import argparse
import json
import sys
from pathlib import Path

from src.wanwan_client.core.app import RuntimeApp
from src.wanwan_client.core.pipeline.text_audio_pipeline import TextAudioPipeline
from src.wanwan_client.core.pipeline.voice_audio_pipeline import VoiceAudioPipeline
from src.wanwan_client.desktop.app import launch_pet_window, launch_voice_chain_window
from src.wanwan_client.desktop.playback import LocalAudioPlayer
from src.wanwan_client.services.llm import LlmService
from src.wanwan_client.services.stt import SttService
from src.wanwan_client.services.tts import TtsService


def build_parser() -> argparse.ArgumentParser:
    """
    最小本地调试入口命令行参数。
    """
    parser = argparse.ArgumentParser(
        prog="wanwan-client",
        description="Minimal local settings/debug entry for RuntimeApp.",
    )
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("show-state", help="Show active profile, profiles, and runtime config.")
    subparsers.add_parser("show-active-profile", help="Show current active profile.")
    subparsers.add_parser("list-profiles", help="List available profiles.")
    subparsers.add_parser("reload-runtime-config", help="Reload runtime config from persisted settings.")
    subparsers.add_parser("save-runtime-config", help="Save current settings and rebuild runtime config.")

    switch_parser = subparsers.add_parser(
        "switch-active-profile",
        help="Switch active profile and persist it.",
    )
    switch_parser.add_argument("profile_id", help="Target profile_id to activate.")

    run_text_audio_parser = subparsers.add_parser(
        "run-text-audio",
        help="Run the minimal real text -> LLM -> TTS -> local playback pipeline.",
    )
    run_text_audio_parser.add_argument("text", help="User text input.")
    run_text_audio_parser.add_argument(
        "--session-id",
        dest="session_id",
        help="Optional session id for the current run.",
    )

    run_llm_text_parser = subparsers.add_parser(
        "run-llm-text",
        help="Run the real text -> LLM stage using current runtime config.",
    )
    run_llm_text_parser.add_argument("text", help="User text input.")
    run_llm_text_parser.add_argument(
        "--session-id",
        dest="session_id",
        help="Optional session id for the current run.",
    )

    run_stt_audio_parser = subparsers.add_parser(
        "run-stt-audio",
        help="Run the real audio -> STT stage using current runtime config.",
    )
    run_stt_audio_parser.add_argument(
        "audio_value",
        help="Audio ref value. For local_path use a local file path. For remote_url use a URL.",
    )
    run_stt_audio_parser.add_argument(
        "--audio-ref-type",
        dest="audio_ref_type",
        choices=["local_path", "remote_url", "base64_inline"],
        default="local_path",
        help="Audio ref type. Defaults to local_path.",
    )
    run_stt_audio_parser.add_argument(
        "--mime-type",
        dest="mime_type",
        default="audio/wav",
        help="Audio mime type. Defaults to audio/wav.",
    )
    run_stt_audio_parser.add_argument(
        "--session-id",
        dest="session_id",
        help="Optional session id for the current run.",
    )
    run_stt_audio_parser.add_argument(
        "--audio-format",
        dest="audio_format",
        help="Optional STT audio_format override, such as wav or webm.",
    )
    run_stt_audio_parser.add_argument(
        "--request-mode",
        dest="request_mode",
        choices=["sync_url", "sync_base64", "async_url", "async_base64"],
        help="Optional STT request mode override.",
    )

    run_tts_text_parser = subparsers.add_parser(
        "run-tts-text",
        help="Run the real text -> TTS stage using current runtime config, then optionally play it locally.",
    )
    run_tts_text_parser.add_argument("text", help="Text to synthesize.")
    run_tts_text_parser.add_argument(
        "--session-id",
        dest="session_id",
        help="Optional session id for the current run.",
    )
    run_tts_text_parser.add_argument(
        "--no-play",
        dest="play_audio",
        action="store_false",
        help="Generate audio only and skip local playback.",
    )
    run_tts_text_parser.set_defaults(play_audio=True)

    run_voice_chain_parser = subparsers.add_parser(
        "run-voice-chain",
        help="Run the minimal real audio -> STT -> LLM -> TTS -> local playback pipeline.",
    )
    run_voice_chain_parser.add_argument("audio_path", help="Local audio file path.")
    run_voice_chain_parser.add_argument(
        "--session-id",
        dest="session_id",
        help="Optional session id for the current run.",
    )
    subparsers.add_parser(
        "run-desktop-voice-window",
        help="Launch the minimal local tkinter window for the voice chain.",
    )
    subparsers.add_parser(
        "run-desktop-pet",
        help="Launch the minimal local tkinter desktop pet shell.",
    )
    return parser


def print_json(data: object) -> None:
    """
    统一输出调试结果。
    """
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps(data, ensure_ascii=False, indent=2))


def main():
    """
    当前主入口只提供最小设置/调试入口，不进入 UI 或主链路。
    """
    parser = build_parser()
    args = parser.parse_args()
    app = RuntimeApp()

    try:
        if args.command in (None, "show-state"):
            print_json(app.get_state_snapshot())
            return

        if args.command == "show-active-profile":
            print(app.get_active_profile())
            return

        if args.command == "list-profiles":
            print_json(list(app.get_available_profiles()))
            return

        if args.command == "switch-active-profile":
            state = app.switch_active_profile(args.profile_id)
            print_json(
                {
                    "active_profile_id": state.active_profile_id,
                    "available_profile_ids": list(state.available_profile_ids),
                }
            )
            return

        if args.command == "reload-runtime-config":
            app.reload_runtime_config()
            print_json(app.get_state_snapshot())
            return

        if args.command == "save-runtime-config":
            app.save_runtime_config()
            print_json(app.get_state_snapshot())
            return

        if args.command == "run-text-audio":
            state = app.load_state()
            pipeline = TextAudioPipeline(runtime_config=state.runtime_config)
            result = pipeline.run(user_text=args.text, session_id=args.session_id)
            print_json(result)
            if result["status"] != "success":
                raise SystemExit(1)
            return

        if args.command == "run-llm-text":
            state = app.load_state()
            service = LlmService(runtime_config=state.runtime_config)
            result = service.generate_reply(
                user_text=args.text,
                session_id=args.session_id,
            )
            print_json(result)
            if result["status"] != "success":
                raise SystemExit(1)
            return

        if args.command == "run-stt-audio":
            state = app.load_state()
            service = SttService(runtime_config=state.runtime_config)
            audio_ref = {
                "type": args.audio_ref_type,
                "value": str(Path(args.audio_value)) if args.audio_ref_type == "local_path" else args.audio_value,
                "mime_type": args.mime_type,
            }
            result = service.transcribe(
                audio_ref=audio_ref,
                session_id=args.session_id,
                provider_id="doubao_flash_stt_primary",
                audio_format=args.audio_format,
                request_mode=args.request_mode,
            )
            print_json(result)
            if result["status"] != "success":
                raise SystemExit(1)
            return

        if args.command == "run-tts-text":
            state = app.load_state()
            service = TtsService(runtime_config=state.runtime_config)
            tts_result = service.synthesize(
                text=args.text,
                session_id=args.session_id,
            )
            result: dict[str, object] = {"tts": tts_result}
            if tts_result["status"] == "success" and args.play_audio:
                audio_ref = tts_result["payload"]["output"]["audio_ref"]
                player = LocalAudioPlayer()
                playback_result = player.play(audio_ref["value"])
                result["playback"] = {
                    "status": "success",
                    "payload": playback_result,
                }
            print_json(result)
            if tts_result["status"] != "success" or (
                args.play_audio and result.get("playback", {}).get("status") != "success"
            ):
                raise SystemExit(1)
            return

        if args.command == "run-voice-chain":
            state = app.load_state()
            pipeline = VoiceAudioPipeline(runtime_config=state.runtime_config)
            result = pipeline.run(audio_path=args.audio_path, session_id=args.session_id)
            print_json(result)
            if result["status"] != "success":
                raise SystemExit(1)
            return

        if args.command == "run-desktop-voice-window":
            launch_voice_chain_window()
            return

        if args.command == "run-desktop-pet":
            launch_pet_window()
            return

        parser.error(f"Unknown command: {args.command}")
    except ValueError as error:
        print(f"error: {error}", file=sys.stderr)
        raise SystemExit(1) from error


if __name__ == "__main__":
    main()
