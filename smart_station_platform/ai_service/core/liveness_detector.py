# smart_station_platform/ai_service/core/liveness_detector.py
import time
import random
from collections import deque
import numpy as np
import logging

# 使用标准 logging
logger = logging.getLogger(__name__)

# --- 挑战动作常量 ---
CHALLENGE_BLINK = "blink"
CHALLENGE_SHAKE_HEAD = "shake_head"
CHALLENGE_NOD_HEAD = "nod_head"
CHALLENGE_OPEN_MOUTH = "open_mouth"

# --- 动作检测的配置参数 ---
# --- FIX: Re-introducing head movements with better logic (and user-defined thresholds) ---
EAR_THRESHOLD = 0.21  # 眼睛宽高比阈值
MOUTH_AR_THRESHOLD = 0.09  # 嘴巴宽高比阈值 (原: 0.2, 0.18)
HEAD_NOD_ANGLE_THRESHOLD = 2.5  # 点头角度范围阈值 (原: 5.0, 4.0)
HEAD_SHAKE_ANGLE_THRESHOLD = 3.0  # 摇头角度范围阈值 (原: 6.0, 5.0)
CONSECUTIVE_FRAMES = 2  # 连续帧数要求

class LivenessSession:
    """管理一次完整的活体检测会话，包括多个挑战。"""
    def __init__(self, timeout=15.0, num_challenges=2):
        self.session_id = f"session_{int(time.time() * 1000)}_{random.randint(1000, 9999)}"
        
        self.action_detectors = {
            "blink": self._detect_blink,
            "open_mouth": self._detect_open_mouth,
            "shake_head": self._detect_shake_head,
            "nod_head": self._detect_nod_head,
        }
        # 若只需要一个挑战，固定为 open_mouth 以降低用户门槛
        if num_challenges == 1:
            self.challenges = [CHALLENGE_OPEN_MOUTH]
        else:
            self.challenges = random.sample(list(self.action_detectors.keys()), k=num_challenges)
        
        # --- 增强: 为每个动作设置更合理的阈值和参数 ---
        # 眼睛宽高比 (EAR) 低于此值表示眨眼
        self.EYE_AR_THRESH = 0.18 
        # 连续多少帧EAR低于阈值才算一次有效的眨眼
        self.EYE_AR_CONSEC_FRAMES = 2
        
        # 嘴巴宽高比 (MAR) 高于此值表示张嘴
        self.MOUTH_AR_THRESH = 0.05
        
        # 头部姿态变化阈值
        self.POSE_HISTORY_LENGTH = 30 # 保持较长的历史记录以适应自然动作
        self.MIN_POSE_FRAMES = 10 # 【核心修复】至少需要10帧数据就开始检测，而不是等30帧
        self.SHAKE_HEAD_ANGLE_THRESH = 5.0 # 左右摇头需要的角度 (度)
        self.NOD_HEAD_ANGLE_THRESH = 4.0 # 上下点头需要的角度 (度)

        self.current_challenge_index = 0
        self.start_time = time.time()
        self.timeout = timeout
        self.is_successful = False
        self.failure_reason = None
        
        # --- 状态跟踪 ---
        # 用于眨眼检测
        self.eye_frame_counter = 0
        # 用于姿态检测
        self.pose_history = deque(maxlen=self.POSE_HISTORY_LENGTH)

        # 修复回归错误: 重新引入 last_frame_time 以进行帧超时检测
        self.last_frame_time = time.time()


    def _generate_challenges(self) -> list:
        """随机生成一个不重复的挑战序列"""
        available_challenges = [
            CHALLENGE_BLINK,
            CHALLENGE_SHAKE_HEAD,
            CHALLENGE_OPEN_MOUTH,
            CHALLENGE_NOD_HEAD
        ]
        # 确保挑战数量不超过可用数量
        num_to_select = min(self.num_challenges, len(available_challenges))
        return random.sample(available_challenges, k=num_to_select)

    def get_current_challenge(self) -> str:
        """获取当前需要用户完成的挑战"""
        if self.is_finished():
            return "finished"
        return self.challenges[self.current_challenge_index]

    def is_timed_out(self) -> bool:
        """检查会话是否因各种原因超时。"""
        # 整体会话超时
        if time.time() - self.start_time > self.timeout:
            self.failure_reason = "session_timeout"
            return True
        
        # 帧处理超时，如果超过5秒没有新帧进来，也认为超时
        if time.time() - self.last_frame_time > 5.0:
            self.failure_reason = "frame_timeout"
            return True
        
        return False

    def is_finished(self) -> bool:
        """检查所有挑战是否已完成"""
        return self.is_successful or self.failure_reason is not None

    def process_frame(self, landmarks, head_pose):
        """
        处理单帧数据，更新动作检测器状态。
        """
        # 更新最后接收到帧的时间
        self.last_frame_time = time.time()

        if self.is_finished():
            return

        current_challenge = self.get_current_challenge()
        detector = self.action_detectors.get(current_challenge)

        if detector:
            # 传递所需的参数
            if current_challenge in ["blink", "open_mouth"]:
                if detector(landmarks):
                    print(f"挑战 '{current_challenge}' 成功!")
                    self._advance_challenge()
            elif current_challenge in ["shake_head", "nod_head"]:
                if detector(head_pose):
                    print(f"挑战 '{current_challenge}' 成功!")
                    self._advance_challenge()

    def _reset_histories(self):
        self.landmarks_history.clear()
        self.eye_aspect_ratio_history.clear()
        self.mouth_aspect_ratio_history.clear()
        self.head_pose_history.clear()

    def dist(self, p1, p2):
        """计算两点之间的欧几里得距离"""
        return np.linalg.norm(p1 - p2)

    def _calculate_ear(self, eye_landmarks):
        """
        计算单只眼睛的眼睛宽高比(EAR)。
        这是一个修正后的、正确的版本，使用 self.dist。
        """
        # 计算眼睛的垂直距离
        v1 = self.dist(eye_landmarks[1], eye_landmarks[5])
        v2 = self.dist(eye_landmarks[2], eye_landmarks[4])
        # 计算眼睛的水平距离
        h = self.dist(eye_landmarks[0], eye_landmarks[3])
        # 计算EAR
        if h > 1e-3:
            ear = (v1 + v2) / (2.0 * h)
        else:
            ear = 0.0
        return ear

    def _detect_blink(self, landmarks):
        """
        检测眨眼动作。
        这是一个修正后的、正确的版本。
        """
        left_eye = landmarks[36:42]
        right_eye = landmarks[42:48]
        
        left_ear = self._calculate_ear(left_eye)
        right_ear = self._calculate_ear(right_eye)
        
        ear = (left_ear + right_ear) / 2.0
        
        if ear < self.EYE_AR_THRESH:
            self.eye_frame_counter += 1
        else:
            if self.eye_frame_counter >= self.EYE_AR_CONSEC_FRAMES:
                print(f"[DEBUG-BLINK-DETECT] BLINK DETECTED! Frames={self.eye_frame_counter}")
                self.eye_frame_counter = 0
                return True # 检测到眨眼
            self.eye_frame_counter = 0
            
        return False

    def _detect_open_mouth(self, landmarks):
        """
        使用嘴巴的垂直与水平关键点距离之比 (MAR) 来检测嘴巴是否张开。
        这是一个更稳定、更准确的方法。
        """
        # 嘴部关键点索引:
        #   - 上唇内侧: 61, 62, 63
        #   - 下唇内侧: 67, 66, 65
        #   - 嘴巴左右角点: 60, 64
        
        # --- 增强: 使用更直接和鲁棒的算法 ---
        # 嘴巴关键点索引:
        # 上唇: 50, 51, 52
        # 下唇: 56, 57, 58
        # 嘴宽: 48, 54
        v_dist = self.dist(landmarks[51], landmarks[57]) # 垂直距离
        h_dist = self.dist(landmarks[48], landmarks[54]) # 水平距离

        if h_dist > 1e-3:
            mar = v_dist / h_dist
        else:
            mar = 0.0
        
        # 使用 print 替换 logger 以确保在所有环境下都能输出
        print(f"[DEBUG-MOUTH-CALC] V_DIST={v_dist:.2f}, H_DIST={h_dist:.2f}, MAR={mar:.4f}")

        if mar > self.MOUTH_AR_THRESH:
            print(f"[DEBUG-MOUTH-DETECT] MOUTH OPEN DETECTED! Current MAR={mar:.4f} > Target > {self.MOUTH_AR_THRESH}")
            return True
        else:
            # 添加此调试信息以查看未通过时的状态
            print(f"[DEBUG-MOUTH-DETECT] Current MAR={mar:.4f} | Target > {self.MOUTH_AR_THRESH}")
            return False

    def _detect_shake_head(self, head_pose):
        """检测摇头动作"""
        # head_pose[1] 是 yaw (偏航角)，表示左右旋转
        yaw = head_pose[1]
        
        self.pose_history.append(yaw)
        
        # 【核心修复】不再需要等待历史记录被填满，只要有足够帧数就开始检测
        if len(self.pose_history) < self.MIN_POSE_FRAMES:
            return False # 需要足够的历史数据

        max_yaw = max(self.pose_history)
        min_yaw = min(self.pose_history)
        
        # 计算角度范围
        angle_range = max_yaw - min_yaw
        
        print(f"[DEBUG-SHAKE] Yaw Range: {angle_range:.2f} | Target > {self.SHAKE_HEAD_ANGLE_THRESH}")

        if angle_range > self.SHAKE_HEAD_ANGLE_THRESH:
            print(f"[DEBUG-SHAKE-DETECT] SHAKE DETECTED! Yaw Range={angle_range:.2f}")
            # 动作完成后清空历史，为下一个动作做准备
            self.pose_history.clear()
            return True
        
        return False

    def _detect_nod_head(self, head_pose):
        """检测点头动作"""
        # head_pose[0] 是 pitch (俯仰角)，表示上下点头
        pitch = head_pose[0]
        
        self.pose_history.append(pitch)

        # 【核心修复】不再需要等待历史记录被填满，只要有足够帧数就开始检测
        if len(self.pose_history) < self.MIN_POSE_FRAMES:
            return False

        max_pitch = max(self.pose_history)
        min_pitch = min(self.pose_history)
        
        angle_range = max_pitch - min_pitch

        print(f"[DEBUG-NOD] Pitch Range: {angle_range:.2f} | Target > {self.NOD_HEAD_ANGLE_THRESH}")

        if angle_range > self.NOD_HEAD_ANGLE_THRESH:
            print(f"[DEBUG-NOD-DETECT] NOD DETECTED! Pitch Range={angle_range:.2f}")
            self.pose_history.clear()
            return True
            
        return False

    def _advance_challenge(self):
        self.current_challenge_index += 1
        # 清空所有状态，为下一个挑战做准备
        self.eye_frame_counter = 0
        self.pose_history.clear()
        
        if self.current_challenge_index >= len(self.challenges):
            self.is_successful = True
            self.failure_reason = None

def get_face_landmarks(frame, face_rect):
    """
    一个辅助函数，用于从图像帧和人脸矩形中提取面部关键点。
    具体的实现将依赖于项目中使用的人脸识别库 (如 dlib, mediapipe)。
    """
    # 这是一个占位符实现，需要后续与 FaceRecognizer 集成
    # 返回一个 numpy 数组，形状为 (68, 2) 或其他格式，以及头部姿态元组 (roll, pitch, yaw)
    pass 