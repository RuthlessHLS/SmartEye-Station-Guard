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
          <p>请确保上传清晰的正面照片，光线充足且面部无遮挡，以确保人脸识别系统的准确性。</p>
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
            <el-form-item label="人脸照片" required>
              <div class="face-capture" :class="{'has-image': imageUrl}">
                <div v-if="!imageUrl" class="capture-placeholder">
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
                  
                  <el-button type="primary" @click="startCamera" class="camera-btn">
                    <el-icon><Camera /></el-icon>
                    使用摄像头拍摄
                  </el-button>
                </div>
                <div v-else class="preview-container">
                  <img :src="imageUrl" class="preview-image" />
                  <div class="preview-actions">
                    <el-button type="danger" @click="removeImage">
                      <el-icon><Delete /></el-icon>
                      重新拍摄/上传
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

    <!-- 摄像头对话框 -->
    <el-dialog
      v-model="showCamera"
      title="拍摄人脸照片"
      width="640px"
      :close-on-click-modal="false"
      :show-close="true"
      class="camera-dialog"
    >
      <div class="camera-container">
        <video
          ref="video"
          :width="640"
          :height="480"
          autoplay
          class="camera-video"
        ></video>
        <canvas
          ref="canvas"
          :width="640"
          :height="480"
          style="display: none"
        ></canvas>
        
        <!-- 添加人脸对齐辅助框 -->
        <div class="face-guide-overlay">
          <div class="face-guide-frame"></div>
          <div class="guide-text">请将面部置于框内，保持正面朝向</div>
        </div>
      </div>
      <template #footer>
        <div class="dialog-footer">
          <el-button @click="closeCamera">取消</el-button>
          <el-button type="primary" @click="captureImage" class="capture-btn">
            <el-icon><Camera /></el-icon>
            拍摄照片
          </el-button>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, nextTick, computed } from 'vue'
import { Plus, Camera, Delete } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import api from '@/api'

// 表单数据
const form = reactive({
  name: '',
  department: '',
  faceImage: null
})

// 表单验证
const formIsValid = computed(() => {
  return form.name && form.department && form.faceImage;
})

// 状态变量
const loading = ref(false)
const imageUrl = ref('')
const showCamera = ref(false)
const video = ref(null)
const canvas = ref(null)
const stream = ref(null)

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
      imageUrl.value = e.target.result
      form.faceImage = file
    }
    reader.readAsDataURL(file)
  } catch (error) {
    ElMessage.error('图片上传失败')
    console.error('Upload error:', error)
  }
}

// 删除已上传的图片
const removeImage = () => {
  imageUrl.value = ''
  form.faceImage = null
}

// 打开摄像头
const startCamera = async () => {
  try {
    // 1. 先把对话框显示出来
    showCamera.value = true

    // 2. 等待下一次DOM更新，确保 <video> 元素已存在
    await nextTick()

    // 3. 现在 video.value 肯定不是 null 了，可以安全操作
    stream.value = await navigator.mediaDevices.getUserMedia({
      video: { 
        width: { ideal: 1280 },
        height: { ideal: 720 },
        facingMode: 'user'
      },
      audio: false
    })
    video.value.srcObject = stream.value
  } catch (error) {
    ElMessage.error('无法访问摄像头')
    console.error('Camera error:', error)
    // 如果出错，记得把对话框关掉
    showCamera.value = false
  }
}

// 关闭摄像头
const closeCamera = () => {
  if (stream.value) {
    stream.value.getTracks().forEach(track => track.stop())
  }
  showCamera.value = false
}

// 拍摄照片
const captureImage = () => {
  const context = canvas.value.getContext('2d')
  context.drawImage(video.value, 0, 0, 640, 480)
  imageUrl.value = canvas.value.toDataURL('image/jpeg')
  
  // 将 Base64 转换为 File 对象
  const base64 = imageUrl.value.split(',')[1]
  const mimeType = 'image/jpeg'
  const bytes = atob(base64)
  const arr = new Uint8Array(bytes.length)
  
  for (let i = 0; i < bytes.length; i++) {
    arr[i] = bytes.charCodeAt(i)
  }
  
  form.faceImage = new File([arr], 'face.jpg', { type: mimeType })
  closeCamera()
  
  // 提示用户照片已拍摄成功
  ElMessage.success('照片拍摄成功')
}

// 提交表单
const submitForm = async () => {
  if (!form.name || !form.department || !form.faceImage) {
    ElMessage.warning('请填写所有必填项并上传人脸照片')
    return
  }

  loading.value = true
  try {
    const formData = new FormData()
    formData.append('username', form.name)
    formData.append('department', form.department)
    formData.append('face_image', form.faceImage)

    await api.ai.registerFace(formData)
    ElMessage.success('人脸注册成功')
    resetForm()
  } catch (error) {
    console.error('Registration error:', error)
    ElMessage.error('人脸注册失败，请重试')
  } finally {
    loading.value = false
  }
}

// 重置表单
const resetForm = () => {
  form.name = ''
  form.department = ''
  form.faceImage = null
  imageUrl.value = ''
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