<template>
  <div class="face-registration">
    <el-card class="registration-card">
      <template #header>
        <div class="card-header">
          <h2>人脸信息录入</h2>
        </div>
      </template>

      <div class="guide-box">
        <div class="guide-icon"><i class="el-icon-info-filled">ℹ️</i></div>
        <div class="guide-content">
          <h4>使用说明</h4>
          <p>请确保上传清晰的正面照片，或在录制视频时保持面部正对、光线充足且无遮挡，以确保系统的准确性。</p>
        </div>
      </div>

      <el-form :model="form" label-width="120px" class="registration-form">
        <div class="form-layout">
          <div class="form-left">
            <el-form-item label="用户名" required>
              <el-input v-model="form.name" placeholder="请输入用户名 (例如: 张三)"></el-input>
            </el-form-item>

            <el-form-item label="部门" required>
              <el-select v-model="form.department" placeholder="请选择部门" class="full-width">
                <el-option label="安保部" value="security"></el-option>
                <el-option label="运营部" value="operations"></el-option>
                <el-option label="技术部" value="technology"></el-option>
                <el-option label="管理部" value="management"></el-option>
              </el-select>
            </el-form-item>
          </div>

          <div class="form-right">
            <el-form-item label="人脸数据" required>
              <div class="face-capture" :class="{'has-image': previewUrl}">
                <div v-if="!previewUrl" class="capture-placeholder">
                  <el-upload
                    class="face-uploader"
                    :show-file-list="false"
                    :before-upload="beforeUpload"
                    :http-request="customUpload"
                    drag
                  >
                    <div class="upload-area">
                      <el-icon class="upload-icon"><Plus /></el-icon>
                      <div class="upload-text">
                        <p>点击或拖拽上传照片</p>
                        <p class="upload-hint">支持JPG/PNG格式，文件大小不超过2MB</p>
                      </div>
                    </div>
                  </el-upload>

                  <div class="divider">或者</div>

                  <el-button type="primary" @click="startRecordingMode" class="camera-btn">
                    <el-icon><Camera /></el-icon>
                    开始录入
                  </el-button>
                </div>
                <div v-else class="preview-container">
                  <img v-if="mediaType === 'image'" :src="previewUrl" class="preview-image" />
                  <video v-if="mediaType === 'video'" :src="previewUrl" class="preview-image" controls autoplay loop muted></video>
                  <div class="preview-actions">
                    <el-button type="danger" @click="removeMedia">
                      <el-icon><Delete /></el-icon>
                      重新选择
                    </el-button>
                  </div>
                </div>
              </div>
            </el-form-item>
          </div>
        </div>

        <el-form-item class="form-buttons">
          <el-button type="primary" @click="submitForm" :loading="loading" :disabled="!formIsValid">
            提交注册
          </el-button>
          <el-button @click="resetForm">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 摄像头录制对话框 -->
    <el-dialog
      v-model="showCamera"
      title="录制人脸视频"
      width="640px"
      :close-on-click-modal="false"
      :show-close="!isRecording"
      @close="closeCamera"
      class="camera-dialog"
    >
      <div class="camera-container">
        <video ref="video" autoplay muted class="camera-video"></video>

        <div class="face-guide-overlay">
          <div class="face-guide-frame"></div>
          <div v-if="!isRecording" class="guide-text">请将面部置于框内，准备开始录制</div>
          <div v-if="isRecording" class="guide-text recording-indicator">
            <div class="recording-dot"></div>
            正在录制... {{ recordingCountdown }}s
          </div>
        </div>
      </div>
      <template #footer>
        <div class="dialog-footer">
          <el-button @click="closeCamera" :disabled="isRecording">取消</el-button>
          <el-button type="primary" @click="startRecording" :disabled="isRecording" class="capture-btn">
            <el-icon><VideoCamera /></el-icon>
            开始录制
          </el-button>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, nextTick, computed } from 'vue'
import { Plus, Camera, Delete, VideoCamera } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '@/api'

// 表单数据
const form = reactive({
  name: '',
  department: '',
  faceMedia: null
})

const mediaType = ref('') // 'image' or 'video'

// 表单验证
const formIsValid = computed(() => {
  return form.name && form.department && form.faceMedia;
})

// 状态变量
const loading = ref(false)
const previewUrl = ref('')
const showCamera = ref(false)
const video = ref(null)
const stream = ref(null)

// 视频录制相关状态
const isRecording = ref(false)
const mediaRecorder = ref(null)
const recordedChunks = ref([])
const recordingCountdown = ref(5)
const countdownTimer = ref(null)


// 文件上传前的验证
const beforeUpload = (file) => {
  const isImage = file.type.startsWith('image/')
  const isLt2M = file.size / 1024 / 1024 < 2

  if (!isImage) {
    ElMessage.error('只能上传图片文件！')
    return false
  }
  if (!isLt2M) {
    ElMessage.error('图片大小不能超过 2MB！')
    return false
  }
  return true
}

// 自定义上传处理
const customUpload = async ({ file }) => {
  try {
    const reader = new FileReader()
    reader.onload = (e) => {
      previewUrl.value = e.target.result
      form.faceMedia = file
      mediaType.value = 'image'
    }
    reader.readAsDataURL(file)
  } catch (error) {
    ElMessage.error('图片预览失败')
    console.error('Upload error:', error)
  }
}

// 删除已上传或录制的媒体
const removeMedia = () => {
  previewUrl.value = ''
  form.faceMedia = null
  mediaType.value = ''
}

// 打开摄像头录制模式
const startRecordingMode = async () => {
  showCamera.value = true
  await nextTick()
  try {
    stream.value = await navigator.mediaDevices.getUserMedia({
      video: {
        width: { ideal: 1280 },
        height: { ideal: 720 },
        facingMode: 'user'
      },
      audio: false
    })
    if (video.value) {
      video.value.srcObject = stream.value
    }
  } catch (error) {
    ElMessage.error('无法访问摄像头，请检查权限。')
    console.error('Camera error:', error)
    showCamera.value = false
  }
}

// 开始录制
const startRecording = () => {
  if (!stream.value) {
    ElMessage.warning('摄像头尚未准备好。')
    return
  }

  isRecording.value = true
  recordedChunks.value = []

  const options = { mimeType: 'video/webm; codecs=vp9' }
  try {
      mediaRecorder.value = new MediaRecorder(stream.value, options)
  } catch(e) {
      console.error('VP9 not supported, falling back to default.', e)
      mediaRecorder.value = new MediaRecorder(stream.value)
  }

  mediaRecorder.value.ondataavailable = (event) => {
    if (event.data.size > 0) {
      recordedChunks.value.push(event.data)
    }
  }

  mediaRecorder.value.onstop = () => {
    const blob = new Blob(recordedChunks.value, { type: 'video/webm' })
    previewUrl.value = URL.createObjectURL(blob)
    form.faceMedia = new File([blob], 'face_video.webm', { type: 'video/webm' })
    mediaType.value = 'video'
    isRecording.value = false
    ElMessage.success('视频录制完成！')
    closeCamera()
  }

  mediaRecorder.value.start()

  // 倒计时
  recordingCountdown.value = 5
  countdownTimer.value = setInterval(() => {
    recordingCountdown.value--
    if (recordingCountdown.value <= 0) {
      stopRecording()
    }
  }, 1000)
}

// 停止录制
const stopRecording = () => {
    if(mediaRecorder.value && mediaRecorder.value.state === 'recording') {
        mediaRecorder.value.stop()
    }
    if (countdownTimer.value) {
        clearInterval(countdownTimer.value)
        countdownTimer.value = null
    }
}

// 关闭摄像头/对话框
const closeCamera = () => {
  stopRecording()
  if (stream.value) {
    stream.value.getTracks().forEach(track => track.stop())
    stream.value = null
  }
  showCamera.value = false
}


// 提交表单
const submitForm = async () => {
  if (!formIsValid.value) {
    ElMessage.warning('请填写所有必填项并提供人脸数据')
    return
  }
  loading.value = true

  try {
    // 步骤1: 检查用户是否存在
    const checkRes = await api.ai.checkFaceExists({
      username: form.name,
      department: form.department,
    });

    if (checkRes.exists) {
      // 步骤2: 如果存在，弹窗确认
      await ElMessageBox.confirm(
        '该用户已存在人脸数据，是否要覆盖或添加新的人脸信息？',
        '用户已存在',
        {
          confirmButtonText: '继续注册',
          cancelButtonText: '取消',
          type: 'warning',
        }
      );
    }
    
    // 步骤3: 执行注册
    const formData = new FormData()
    formData.append('username', form.name)
    formData.append('department', form.department)

    if (mediaType.value === 'image') {
      formData.append('face_image', form.faceMedia)
      await api.ai.registerFace(formData)
    } else if (mediaType.value === 'video') {
      formData.append('video_file', form.faceMedia)
      await api.ai.registerFace(formData)
    }

    ElMessage.success('人脸注册请求已提交成功')
    resetForm()
  } catch (error) {
    // 如果用户点击了“取消”或API调用失败
    if (error === 'cancel') {
      ElMessage.info('已取消注册操作');
    } else {
      console.error('Registration error:', error)
      const errorMsg = error.response?.data?.detail || error.response?.data?.message || '人脸注册失败，请检查后端服务或视频/图片质量'
      ElMessage.error(errorMsg)
    }
  } finally {
    loading.value = false
  }
}

// 重置表单
const resetForm = () => {
  form.name = ''
  form.department = ''
  form.faceMedia = null
  previewUrl.value = ''
  mediaType.value = ''
}
</script>

<style scoped>
.face-registration {
  padding: 20px;
  max-width: 1000px;
  margin: 0 auto;
}

.registration-card {
  margin-bottom: 20px;
  box-shadow: 0 2px 12px 0 rgba(0, 0, 0, 0.1);
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.card-header h2 {
  font-size: 20px;
  color: #303133;
  margin: 0;
}

.registration-form {
  margin-top: 20px;
}

.guide-box {
  background-color: #ecf8ff;
  border-radius: 4px;
  padding: 12px 16px;
  margin-bottom: 20px;
  display: flex;
  align-items: flex-start;
}

.guide-icon {
  font-size: 20px;
  color: #409EFF;
  margin-right: 12px;
  margin-top: 2px;
}

.guide-content h4 {
  margin: 0 0 8px;
  font-size: 16px;
  color: #303133;
}

.guide-content p {
  margin: 0;
  font-size: 14px;
  color: #606266;
  line-height: 1.5;
}

.form-layout {
  display: flex;
  flex-wrap: wrap;
  gap: 20px;
}

.form-left, .form-right {
  flex: 1;
  min-width: 300px;
}

.form-buttons {
  margin-top: 30px;
  display: flex;
  justify-content: center;
}

.full-width {
  width: 100%;
}

.face-capture {
  width: 100%;
  min-height: 300px;
  border: 2px dashed #dcdfe6;
  border-radius: 6px;
  display: flex;
  justify-content: center;
  align-items: center;
  position: relative;
  transition: all 0.3s;
}

.face-capture.has-image {
  border-style: solid;
  border-color: #409EFF;
}

.capture-placeholder {
  text-align: center;
  width: 100%;
  padding: 20px;
}

.face-uploader {
  width: 100%;
  margin-bottom: 15px;
}

.upload-area {
  padding: 30px;
  cursor: pointer;
  text-align: center;
  border-radius: 4px;
  background-color: #fafafa;
  transition: all 0.3s;
}

.upload-area:hover {
  background-color: #f5f7fa;
}

.upload-icon {
  font-size: 40px;
  color: #8c939d;
  margin-bottom: 10px;
}

.upload-text {
  color: #606266;
}

.upload-hint {
  font-size: 12px;
  color: #909399;
  margin-top: 5px;
}

.divider {
  position: relative;
  text-align: center;
  color: #909399;
  font-size: 14px;
  margin: 15px 0;
}

.divider::before, .divider::after {
  content: '';
  position: absolute;
  top: 50%;
  width: 30%;
  height: 1px;
  background-color: #dcdfe6;
}

.divider::before {
  left: 0;
}

.divider::after {
  right: 0;
}

.camera-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto;
}

.camera-btn i {
  margin-right: 5px;
}

.preview-container {
  width: 100%;
  padding: 10px;
  text-align: center;
}

.preview-image {
  max-width: 100%;
  max-height: 300px;
  border-radius: 4px;
  box-shadow: 0 2px 12px 0 rgba(0, 0, 0, 0.1);
  background-color: #000;
}

.preview-actions {
  margin-top: 15px;
  display: flex;
  justify-content: center;
}

.camera-container {
  width: 100%;
  position: relative;
  border-radius: 4px;
  overflow: hidden;
  box-shadow: 0 2px 12px 0 rgba(0, 0, 0, 0.1);
  background: #000;
}

.camera-video {
  width: 100%;
  display: block;
}

/* 人脸对齐辅助框 */
.face-guide-overlay {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  pointer-events: none;
}

.face-guide-frame {
  width: 220px;
  height: 300px;
  border: 3px solid rgba(255, 255, 255, 0.7);
  border-radius: 50% 50% 50% 50% / 60% 60% 40% 40%;
  box-shadow: 0 0 0 999px rgba(0, 0, 0, 0.3);
}

.guide-text {
  color: white;
  text-shadow: 0 1px 2px rgba(0, 0, 0, 0.5);
  margin-top: 20px;
  font-size: 16px;
  background: rgba(0, 0, 0, 0.5);
  padding: 8px 16px;
  border-radius: 4px;
}

.recording-indicator {
    display: flex;
    align-items: center;
    background-color: #f56c6c;
}

.recording-dot {
    width: 10px;
    height: 10px;
    background-color: white;
    border-radius: 50%;
    margin-right: 8px;
    animation: pulse-rec 1.5s infinite;
}

@keyframes pulse-rec {
    0% { opacity: 1; }
    50% { opacity: 0.4; }
    100% { opacity: 1; }
}

.camera-dialog :deep(.el-dialog__body) {
  padding: 0;
}

.dialog-footer {
  display: flex;
  justify-content: space-between;
  padding: 15px 20px;
}

.capture-btn {
  display: flex;
  align-items: center;
}

.capture-btn i {
  margin-right: 5px;
}

@media (max-width: 768px) {
  .face-registration {
    padding: 10px;
  }

  .registration-card {
    margin-bottom: 10px;
  }

  .form-layout {
    flex-direction: column;
    gap: 0;
  }
}
</style>
