from src.wanwan_client.core.app import RuntimeApp


def main():
    """
    当前主入口只验证配置应用最小入口可用。
    """
    app = RuntimeApp()
    state = app.load_state()
    print(
        "wanwan-client runtime is ready: "
        f"active_profile={state.active_profile_id}, "
        f"available_profiles={list(state.available_profile_ids)}"
    )

if __name__ == "__main__":
    main()
