import face_recognition
import os

def test_face_images(known_faces_dir):
    print(f"开始测试目录: {known_faces_dir}")
    
    if not os.path.exists(known_faces_dir):
        print(f"错误: 目录不存在: {known_faces_dir}")
        return
        
    total_images = 0
    successful_images = 0
    
    for person_name in os.listdir(known_faces_dir):
        person_dir = os.path.join(known_faces_dir, person_name)
        if os.path.isdir(person_dir):
            print(f"\n检查 {person_name} 的照片:")
            for filename in os.listdir(person_dir):
                if filename.lower().endswith(('.png', '.jpg', '.jpeg')):
                    total_images += 1
                    image_path = os.path.join(person_dir, filename)
                    try:
                        # 加载图片
                        face_image = face_recognition.load_image_file(image_path)
                        # 尝试检测人脸
                        face_locations = face_recognition.face_locations(face_image)
                        # 尝试提取人脸特征
                        face_encodings = face_recognition.face_encodings(face_image, face_locations)
                        
                        if len(face_locations) == 0:
                            print(f"  ❌ {filename}: 未检测到人脸")
                        elif len(face_locations) > 1:
                            print(f"  ⚠️ {filename}: 检测到多个人脸 ({len(face_locations)}个)")
                            successful_images += 1
                        else:
                            print(f"  ✅ {filename}: 成功检测到1个人脸")
                            successful_images += 1
                            
                    except Exception as e:
                        print(f"  ❌ {filename}: 处理失败 - {str(e)}")
    
    print(f"\n总结:")
    print(f"总共图片数: {total_images}")
    print(f"成功处理数: {successful_images}")
    print(f"成功率: {(successful_images/total_images*100):.1f}% 如果成功率较低，请检查图片质量")

if __name__ == "__main__":
    known_faces_dir = "G:/ai_assets/known_faces"
    test_face_images(known_faces_dir) 