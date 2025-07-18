from rest_framework import serializers
from .models import Camera, DangerousArea


class CameraSerializer(serializers.ModelSerializer):
    """摄像头序列化器"""
    
    class Meta:
        model = Camera
        fields = [
            'id', 'name', 'rtsp_url', 'location_desc', 
            'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class DangerousAreaSerializer(serializers.ModelSerializer):
    """危险区域序列化器"""
    
    camera_name = serializers.CharField(source='camera.name', read_only=True)
    
    class Meta:
        model = DangerousArea
        fields = '__all__'


class CameraDetailSerializer(CameraSerializer):
    """摄像头详情序列化器，包含关联的危险区域"""
    
    dangerous_areas = DangerousAreaSerializer(many=True, read_only=True)
    
    class Meta(CameraSerializer.Meta):
        fields = CameraSerializer.Meta.fields + ['dangerous_areas']


class DangerousAreaCreateSerializer(serializers.ModelSerializer):
    """危险区域创建序列化器"""
    
    # 允许仅通过 camera_id 指定摄像头，camera 字段本身设为非必填以绕过字段级校验
    camera = serializers.PrimaryKeyRelatedField(queryset=Camera.objects.all(), required=False, allow_null=True, write_only=True)
    camera_id = serializers.CharField(write_only=True, required=False)
    
    class Meta:
        model = DangerousArea
        fields = [
            'camera', 'camera_id', 'name', 'coordinates',
            'min_distance_threshold', 'time_in_area_threshold', 'is_active'
        ]
    
    def validate_coordinates(self, value):
        """验证坐标格式"""
        if not isinstance(value, list):
            raise serializers.ValidationError("坐标必须是列表格式")
        
        if len(value) < 3:
            raise serializers.ValidationError("多边形至少需要3个坐标点")
        
        for coord in value:
            if not isinstance(coord, list) or len(coord) != 2:
                raise serializers.ValidationError("每个坐标点必须是包含x,y两个值的列表")
            
            if not all(isinstance(x, (int, float)) for x in coord):
                raise serializers.ValidationError("坐标值必须是数字")
        
        return value
    
    def validate(self, data):
        """验证数据并处理摄像头ID"""
        camera_id = data.get('camera_id')
        camera = data.get('camera')
        
        # 如果提供了camera_id，优先使用它来查找摄像头
        if camera_id:
            try:
                if camera_id.isdigit():
                    # 如果是数字，按ID查找
                    camera = Camera.objects.get(id=camera_id)
                else:
                    # 如果是字符串，按名称查找
                    camera = Camera.objects.get(name=camera_id)
                data['camera'] = camera
            except Camera.DoesNotExist:
                raise serializers.ValidationError(f"找不到摄像头: {camera_id}")
        elif not camera:
            # 如果既没有camera_id也没有camera对象，报错
            raise serializers.ValidationError("必须提供camera_id或camera对象")
        
        return data