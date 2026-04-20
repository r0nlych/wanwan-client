/**
 * 聊天页面前端脚本
 * 功能：处理录音按钮的点击交互，使用浏览器原生 MediaRecorder API 实现录音
 *
 * 关键状态变量说明：
 * - isRecording: 标记当前是否正在录音（true=录音中，false=未录音）
 * - mediaRecorder: 浏览器 MediaRecorder 实例，用于控制录音开始/停止
 * - audioChunks: 数组，用于存放录音过程中的音频数据片段
 * - stream: 麦克风媒体流，录音结束后需要主动释放
 */

(function() {
  // ==================== 状态变量 ====================
  // 标记是否正在录音
  var isRecording = false;

  // 获取页面元素：录音按钮、状态显示区
  var recordBtn = document.getElementById('record-btn');
  var statusDiv = document.getElementById('status');

  // 浏览器 MediaRecorder 实例，控制录音的开始和停止
  var mediaRecorder = null;

  // 存放录音过程中产生的音频数据片段
  var audioChunks = [];

  // 麦克风媒体流，录音结束后需要调用 getTracks().stop() 释放
  var stream = null;


  // ==================== 事件绑定 ====================
  // 给录音按钮绑定点击事件
  // 点击后的处理逻辑：
  //   - 如果当前未录音 -> 调用 startRecording() 开始录音
  //   - 如果当前正在录音 -> 调用 stopRecording() 停止录音
  recordBtn.addEventListener('click', function() {
    if (!isRecording) {
      startRecording();
    } else {
      stopRecording();
    }
  });


  // ==================== 开始录音 ====================
  // 作用：请求麦克风权限，创建 MediaRecorder，开始收集音频数据
  function startRecording() {

    // 调用浏览器 API 请求麦克风权限
    // 这会弹出浏览器授权提示框，让用户选择是否允许使用麦克风
    navigator.mediaDevices.getUserMedia({ audio: true })
      .then(function(s) {
        // ----- 权限获取成功，开始初始化录音 -----

        // 保存媒体流引用，停止录音时需要用这个来释放麦克风
        stream = s;

        // 创建 MediaRecorder 实例，参数是麦克风媒体流
        // 浏览器会自动选择合适的音频编码格式
        mediaRecorder = new MediaRecorder(stream);

        // 重置音频数据数组，每次开始新录音都要清空
        audioChunks = [];


        // ----- 设置 MediaRecorder 的事件处理 -----

        // ondataavailable：当有音频数据可用了就会被调用
        // 录音过程中，浏览器会多次触发这个事件，把音频片段传给我们
        mediaRecorder.ondataavailable = function(e) {
          // 只有当数据大小大于 0 时才收集（避免空数据）
          if (e.data.size > 0) {
            audioChunks.push(e.data);
          }
        };

        // onstop：当调用 mediaRecorder.stop() 后，这个事件会被触发
        // 意味着录音已经结束，可以处理最终的音频数据了
        mediaRecorder.onstop = function() {
          // 将所有音频片段合并成一个完整的 Blob 对象
          // type: 'audio/webm' 是浏览器默认的录音格式
          const audioBlob = new Blob(audioChunks, { type: 'audio/webm' });

          // 在浏览器控制台输出录音结果（调试用）
          console.log('录音成功:', audioBlob);
          console.log('Blob 大小:', audioBlob.size, '字节');
          console.log('Blob 类型:', audioBlob.type);
        };

        // 调用 start() 正式开始录音
        // 浏览器开始采集麦克风音频数据
        mediaRecorder.start();

        // ----- 更新页面 UI 状态 -----
        isRecording = true;
        recordBtn.textContent = '⏹ 停止录音';
        statusDiv.textContent = '录音中...';
      })
      .catch(function(err) {
        // ----- 权限获取失败，或者麦克风出错了 -----
        console.error('无法获取麦克风:', err);
        statusDiv.textContent = '无法访问麦克风';
      });
  }


  // ==================== 停止录音 ====================
  // 作用：停止 MediaRecorder，释放媒体流，更新页面状态
  function stopRecording() {

    // 先检查 MediaRecorder 是否存在且当前正在录音
    // 避免在非录音状态下调用 stop() 报错
    if (mediaRecorder && mediaRecorder.state !== 'inactive') {

      // 调用 stop() 停止录音
      // 停止后，浏览器会触发 onstop 事件，我们在那里处理最终数据
      mediaRecorder.stop();

      // 释放麦克风媒体流
      // 非常重要！不调用的话麦克风会一直被占用，其他应用无法使用
      if (stream) {
        stream.getTracks().forEach(track => track.stop());
        stream = null;
      }

      // ----- 更新页面 UI 状态 -----
      isRecording = false;
      recordBtn.textContent = '🎤 录音';
      statusDiv.textContent = '已停止';
    }
  }
})();

