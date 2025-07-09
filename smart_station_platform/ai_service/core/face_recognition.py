# ai_service/core/face_recognition.py
import torch
from facenet_pytorch import MTCNN, InceptionResnetV1
from PIL import Image
from torchvision import transforms
import os


class FaceRecognizer:
    def __init__(self, face_db_path, device=None):
        """
        初始化人脸识别器。
        Args:
            face_db_path (str): 人脸数据库的路径。
        """
        if device is None:
            self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        else:
            self.device = device

        print(f"Face Recognizer using device: {self.device}")

        # 1. 加载预训练的人脸检测和识别模型
        # MTCNN用于检测图片中的人脸位置
        self.mtcnn = MTCNN(keep_all=True, device=self.device)
        # InceptionResnetV1用于为每个人脸生成一个512维的特征向量（embedding）
        self.resnet = InceptionResnetV1(pretrained='vggface2').eval().to(self.device)

        # 2. 加载并处理人脸数据库
        self.known_face_embeddings = []
        self.known_face_names = []
        self.load_face_db(face_db_path)

    def load_face_db(self, db_path):
        """
        加载人脸数据库，为每个已知人员生成并存储人脸特征向量。
        """
        if not os.path.isdir(db_path):
            print(f"警告: 人脸数据库路径不存在: {db_path}")
            return

        print("正在加载人脸数据库...")
        for person_name in os.listdir(db_path):
            person_dir = os.path.join(db_path, person_name)
            if not os.path.isdir(person_dir):
                continue

            for img_name in os.listdir(person_dir):
                img_path = os.path.join(person_dir, img_name)
                try:
                    img = Image.open(img_path).convert('RGB')
                    # 使用MTCNN找到图片中的人脸
                    face_tensor = self.mtcnn(img)
                    if face_tensor is not None:
                        # 为检测到的人脸生成特征向量，并关闭梯度计算
                        with torch.no_grad():
                            embedding = self.resnet(face_tensor.to(self.device))
                        self.known_face_embeddings.append(embedding)
                        self.known_face_names.append(person_name)
                        print(f"  - 已加载 '{person_name}' 的人脸特征来自 {img_name}")
                except Exception as e:
                    print(f"处理图片 {img_path} 时出错: {e}")

        if not self.known_face_embeddings:
            print("警告: 人脸数据库为空或加载失败。")
        else:
            self.known_face_embeddings = torch.cat(self.known_face_embeddings, dim=0)
            print("人脸数据库加载完毕。")

    def recognize_faces(self, image_path, distance_threshold=0.9):
        """
        识别给定图片中的所有人脸。
        Args:
            image_path (str): 待识别图片的路径。
            distance_threshold (float): 人脸匹配的距离阈值，越小越严格。
        Returns:
            list: 包含每个检测到的人脸信息（坐标、姓名、置信度）的列表。
        """
        results = []
        try:
            img = Image.open(image_path).convert('RGB')
        except Exception as e:
            print(f"无法打开图片 {image_path}: {e}")
            return []

        # 1. 检测图片中的所有人脸及其坐标
        boxes, _ = self.mtcnn.detect(img)
        if boxes is None:
            return []  # 没有检测到人脸

        # 2. 为每个检测到的人脸生成特征向量
        # mtcnn()直接返回裁剪和对齐后的人脸张量
        face_tensors = self.mtcnn(img)
        if face_tensors is None:
            return []

        with torch.no_grad():
            unknown_embeddings = self.resnet(face_tensors.to(self.device))

        # 3. 与数据库中的已知人脸进行比对
        for i, unknown_emb in enumerate(unknown_embeddings):
            if not self.known_face_embeddings.nelement():  # 检查数据库是否为空
                distances = torch.tensor([])
            else:
                # 计算未知人脸与数据库中所有人脸的余弦距离
                distances = (unknown_emb - self.known_face_embeddings).norm(dim=1)

            # 找到最小距离及其索引
            min_dist, min_idx = torch.min(distances, dim=0) if len(distances) > 0 else (None, None)

            name = "stranger"
            confidence = 0.0

            if min_dist is not None and min_dist.item() < distance_threshold:
                name = self.known_face_names[min_idx.item()]
                # 将距离转换为一个0-1的置信度（非严格）
                confidence = 1.0 - (min_dist.item() / distance_threshold)

            results.append({
                "name": name,
                "confidence": round(confidence, 2),
                "coordinates": [round(c, 2) for c in boxes[i].tolist()]
            })

        return results