<template>
  <div class="face-registration">
    <el-card class="registration-card">
      <template #header>
        <div class="card-header">
          <h2>人脸注册</h2>
        </div>
      </template>

      <el-form :model="form" label-width="120px" class="registration-form">
        <el-form-item label="姓名">
          <el-input v-model="form.name" placeholder="请输入姓名"></el-input>
        </el-form-item>

        <el-form-item label="工号">
          <el-input v-model="form.employeeId" placeholder="请输入工号"></el-input>
        </el-form-item>

        <el-form-item label="部门">
          <el-select v-model="form.department" placeholder="请选择部门" class="full-width">
            <el-option label="安保部" value="security"></el-option>
            <el-option label="运营部" value="operations"></el-option>
            <el-option label="技术部" value="technology"></el-option>
            <el-option label="管理部" value="management"></el-option>
          </el-select>
        </el-form-item>

        <el-form-item label="人脸照片">
          <div class="face-capture">
            <div v-if="!imageUrl" class="capture-placeholder">
              <el-upload
                class="face-uploader"
                :show-file-list="false"
                :before-upload="beforeUpload"
                :http-request="customUpload"
              >
                <div class="upload-area">
                  <el-icon class="upload-icon"><Plus /></el-icon>
                  <div class="upload-text">点击上传照片或使用摄像头拍摄</div>
                </div>
              </el-upload>
              <el-button type="primary" @click="startCamera" class="camera-btn">
                <el-icon><Camera /></el-icon>
                打开摄像头
              </el-button>
            </div>
            <div v-else class="preview-container">
              <img :src="imageUrl" class="preview-image" />
              <div class="preview-actions">
                <el-button type="danger" @click="removeImage">删除照片</el-button>
              </div>
            </div>
          </div>
        </el-form-item>

        <el-form-item>
          <el-button type="primary" @click="submitForm" :loading="loading">
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
      </div>
      <template #footer>
        <div class="dialog-footer">
          <el-button @click="closeCamera">取消</el-button>
          <el-button type="primary" @click="captureImage">拍摄</el-button>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { Plus, Camera } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import api from '@/api'

// 表单数据
const form = reactive({
  name: '',
  employeeId: '',
  department: '',
  faceImage: null
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
    stream.value = await navigator.mediaDevices.getUserMedia({
      video: true,
      audio: false
    })
    video.value.srcObject = stream.value
    showCamera.value = true
  } catch (error) {
    ElMessage.error('无法访问摄像头')
    console.error('Camera error:', error)
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
}

// 提交表单
const submitForm = async () => {
  if (!form.name || !form.employeeId || !form.department || !form.faceImage) {
    ElMessage.warning('请填写所有必填项并上传人脸照片')
    return
  }

  loading.value = true
  try {
    const formData = new FormData()
    formData.append('name', form.name)
    formData.append('employee_id', form.employeeId)
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
  form.employeeId = ''
  form.department = ''
  form.faceImage = null
  imageUrl.value = ''
}
</script>

<style scoped>
.face-registration {
  padding: 20px;
  max-width: 800px;
  margin: 0 auto;
}

.registration-card {
  margin-bottom: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.registration-form {
  margin-top: 20px;
}

.full-width {
  width: 100%;
}

.face-capture {
  width: 100%;
  min-height: 200px;
  border: 2px dashed #dcdfe6;
  border-radius: 6px;
  display: flex;
  justify-content: center;
  align-items: center;
  position: relative;
}

.capture-placeholder {
  text-align: center;
  width: 100%;
}

.face-uploader {
  width: 100%;
}

.upload-area {
  padding: 20px;
  cursor: pointer;
}

.upload-area:hover {
  background-color: #f5f7fa;
}

.upload-icon {
  font-size: 28px;
  color: #8c939d;
  margin-bottom: 10px;
}

.upload-text {
  color: #606266;
  font-size: 14px;
}

.camera-btn {
  margin-top: 15px;
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
}

.preview-actions {
  margin-top: 10px;
}

.camera-container {
  width: 100%;
  display: flex;
  justify-content: center;
  align-items: center;
}

.camera-video {
  max-width: 100%;
  border-radius: 4px;
}

@media (max-width: 768px) {
  .face-registration {
    padding: 10px;
  }
  
  .registration-card {
    margin-bottom: 10px;
  }
  
  .preview-image {
    max-height: 200px;
  }
}
</style> 