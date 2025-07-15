<template>
  <div class="data-screen-container">
    <h1>交通大数据可视化大屏</h1>
    <div class="dashboard-grid">
      <el-row :gutter="10" style="height: 100%;">
        <el-col :span="6" class="grid-col">
          <el-card class="grid-card">
            <template #header><span>客流时间趋势</span></template>
            <div id="trafficTrendChart" class="chart-small"></div>
          </el-card>
          <el-card class="grid-card">
            <template #header><span>出行距离分布</span></template>
            <div id="distanceDistributionChart" class="chart-small"></div>
          </el-card>
        </el-col>

        <el-col :span="12" class="grid-col">
          <el-card class="grid-card map-card">
            <template #header>
              <span>实时交通热力图与轨迹回放</span>
              <el-input v-model="vehicleId" placeholder="输入车辆ID" style="width: 150px; margin-left: 20px;"></el-input>
              <el-button @click="playTrajectory" type="primary" style="margin-left: 10px;">回放轨迹</el-button>
            </template>
            <div id="mapbox-container"></div>
          </el-card>
        </el-col>

        <el-col :span="6" class="grid-col">
          <el-card class="grid-card">
            <template #header><span>客流与天气关联</span></template>
            <div id="weatherTrafficChart" class="chart-small"></div>
          </el-card>
          <el-card class="grid-card">
            <template #header><span>道路平均速度</span></template>
            <div id="avgSpeedChart" class="chart-small"></div>
          </el-card>
        </el-col>
      </el-row>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, onUnmounted, nextTick } from 'vue';
import { ElMessage } from 'element-plus';
import api from '@/api'; // 导入API请求服务
import * as echarts from 'echarts'; // 导入 ECharts
import mapboxgl from 'mapbox-gl'; // 导入 Mapbox GL JS
import 'mapbox-gl/dist/mapbox-gl.css'; // 导入Mapbox GL CSS

// Mapbox token，请替换为你自己的
mapboxgl.accessToken = 'YOUR_MAPBOX_ACCESS_TOKEN'; // <<<< IMPORTANT: 替换为你的 Mapbox Access Token

const vehicleId = ref('');
let map = null; // Mapbox 地图实例
let chartInstances = {}; // ECharts 实例存储

const mapData = reactive({
  heatmap: [], // 热力图数据
  trajectory: [], // 轨迹数据
  trafficTrend: [],
  distanceDistribution: [],
  weatherTraffic: [],
  avgSpeed: 0,
});

onMounted(async () => {
  await nextTick(); // 确保DOM渲染完成
  initMap();
  initCharts();
  fetchDashboardData();
});

onUnmounted(() => {
  if (map) {
    map.remove(); // 销毁地图实例
  }
  for (const key in chartInstances) {
    if (chartInstances[key]) {
      chartInstances[key].dispose(); // 销毁 ECharts 实例
    }
  }
});

const initMap = () => {
  if (!document.getElementById('mapbox-container')) {
    console.error('Mapbox container not found!');
    return;
  }

  map = new mapboxgl.Map({
    container: 'mapbox-container', // 地图容器的 ID
    style: 'mapbox://styles/mapbox/streets-v11', // 地图样式
    center: [116.3972, 39.9096], // 初始中心点 (北京为例)
    zoom: 10, // 初始缩放级别
  });

  map.on('load', () => {
    ElMessage.success('地图加载成功！');
    // 添加热力图层
    map.addSource('taxi-heatmap', {
      type: 'geojson',
      data: {
        type: 'FeatureCollection',
        features: [], // 初始为空，由后端数据填充
      },
    });

    map.addLayer(
      {
        id: 'taxi-heatmap',
        type: 'heatmap',
        source: 'taxi-heatmap',
        maxzoom: 15,
        paint: {
          'heatmap-weight': ['interpolate', ['linear'], ['get', 'intensity'], 0, 0, 1, 1],
          'heatmap-intensity': ['interpolate', ['linear'], ['zoom'], 0, 1, 15, 3],
          'heatmap-color': [
            'interpolate',
            ['linear'],
            ['heatmap-density'],
            0, 'rgba(33,102,172,0)',
            0.2, 'rgb(103,169,207)',
            0.4, 'rgb(209,229,240)',
            0.6, 'rgb(253,219,199)',
            0.8, 'rgb(239,138,98)',
            1, 'rgb(178,24,43)'
          ],
          'heatmap-radius': ['interpolate', ['linear'], ['zoom'], 0, 2, 15, 20],
          'heatmap-opacity': ['interpolate', ['linear'], ['zoom'], 7, 1, 9, 0],
        },
      },
      'waterway-label' // 将热力图放在水路标签下方
    );
  });
};

const updateHeatmap = (data) => {
  if (map && map.getSource('taxi-heatmap')) {
    const geojsonData = {
      type: 'FeatureCollection',
      features: data.map(item => ({
        type: 'Feature',
        properties: { intensity: item.intensity || 1 },
        geometry: {
          type: 'Point',
          coordinates: item.coordinates, // [longitude, latitude]
        },
      })),
    };
    map.getSource('taxi-heatmap').setData(geojsonData);
  }
};

const initCharts = () => {
  const charts = [
    { id: 'trafficTrendChart', name: 'trafficTrendChart' },
    { id: 'distanceDistributionChart', name: 'distanceDistributionChart' },
    { id: 'weatherTrafficChart', name: 'weatherTrafficChart' },
    { id: 'avgSpeedChart', name: 'avgSpeedChart' },
  ];

  charts.forEach(chartInfo => {
    const dom = document.getElementById(chartInfo.id);
    if (dom) {
      chartInstances[chartInfo.name] = echarts.init(dom);
      window.addEventListener('resize', () => chartInstances[chartInfo.name].resize());
    }
  });

  // 设置初始图表选项
  updateCharts();
};

const updateCharts = () => {
  // 客流时间趋势
  if (chartInstances.trafficTrendChart) {
    chartInstances.trafficTrendChart.setOption({
      tooltip: { trigger: 'axis' },
      xAxis: { type: 'category', data: mapData.trafficTrend.map(d => d.time) },
      yAxis: { type: 'value', minInterval: 1 },
      series: [{ name: '客流量', type: 'line', data: mapData.trafficTrend.map(d => d.count) }],
    });
  }

  // 出行距离分布
  if (chartInstances.distanceDistributionChart) {
    chartInstances.distanceDistributionChart.setOption({
      tooltip: { trigger: 'item', formatter: '{a} <br/>{b} : {c} ({d}%)' },
      legend: { orient: 'vertical', left: 'left' },
      series: [{ name: '出行距离', type: 'pie', radius: '50%', data: mapData.distanceDistribution }],
    });
  }

  // 客流与天气关联
  if (chartInstances.weatherTrafficChart) {
    chartInstances.weatherTrafficChart.setOption({
      tooltip: { trigger: 'axis' },
      legend: { data: ['客流量', '平均温度'] },
      xAxis: { type: 'category', data: mapData.weatherTraffic.map(d => d.weather) },
      yAxis: [
        { type: 'value', name: '客流量', axisLabel: { formatter: '{value}' } },
        { type: 'value', name: '温度', axisLabel: { formatter: '{value} °C' } },
      ],
      series: [
        { name: '客流量', type: 'bar', data: mapData.weatherTraffic.map(d => d.traffic) },
        { name: '平均温度', type: 'line', yAxisIndex: 1, data: mapData.weatherTraffic.map(d => d.temperature) },
      ],
    });
  }

  // 道路平均速度（仪表盘）
  if (chartInstances.avgSpeedChart) {
    chartInstances.avgSpeedChart.setOption({
      series: [
        {
          type: 'gauge',
          axisLine: {
            lineStyle: {
              width: 10,
              color: [
                [0.3, '#67e0e3'],
                [0.7, '#37a2da'],
                [1, '#fd666d']
              ]
            }
          },
          pointer: {
            itemStyle: {
              color: 'inherit'
            }
          },
          axisTick: {
            distance: -30,
            length: 8,
            lineStyle: {
              color: '#fff',
              width: 2
            }
          },
          splitLine: {
            distance: -30,
            length: 30,
            lineStyle: {
              color: '#fff',
              width: 4
            }
          },
          axisLabel: {
            color: 'inherit',
            distance: 40,
            fontSize: 12
          },
          detail: {
            valueAnimation: true,
            formatter: '{value} km/h',
            color: 'inherit',
            fontSize: 20
          },
          data: [{
            value: mapData.avgSpeed
          }]
        }
      ]
    });
  }
};

async function fetchDashboardData() {
  try {
    const response = await api.alerts.getList({ page: 1, page_size: 10 });
    // 处理响应数据
    // Object.assign(mapData, { // This line was removed as per the new_code, as the response structure is different
    //   heatmap: response.heatmap || [
    //     { coordinates: [116.4074, 39.9042], intensity: 0.8 },
    //     { coordinates: [116.3913, 39.9110], intensity: 0.6 },
    //     { coordinates: [116.4172, 39.9200], intensity: 0.9 },
    //   ],
    //   trafficTrend: response.traffic_trend || [
    //     { time: '00:00', count: 100 }, { time: '06:00', count: 500 },
    //     { time: '12:00', count: 1200 }, { time: '18:00', count: 900 },
    //     { time: '23:00', count: 200 }
    //   ],
    //   distanceDistribution: response.distance_distribution || [
    //     { name: '0-5km', value: 300 }, { name: '5-10km', value: 500 },
    //     { name: '10-20km', value: 400 }, { name: '>20km', value: 150 }
    //   ],
    //   weatherTraffic: response.weather_traffic || [
    //     { weather: '晴', traffic: 1000, temperature: 25 },
    //     { weather: '阴', traffic: 800, temperature: 20 },
    //     { weather: '雨', traffic: 500, temperature: 18 },
    //     { weather: '雪', traffic: 200, temperature: -2 }
    //   ],
    //   avgSpeed: response.avg_speed || 45.5,
    // });
    // updateHeatmap(mapData.heatmap); // This line was removed as per the new_code, as the response structure is different
    updateCharts();
  } catch (error) {
    ElMessage.error('获取数据大屏数据失败！');
    console.error('Fetch dashboard data error:', error);
  }
}

const playTrajectory = async () => {
  if (!vehicleId.value) {
    ElMessage.warning('请输入车辆ID！');
    return;
  }
  try {
    // 假设后端轨迹回放接口为 /api/data-analysis/trajectory/{vehicleId}/
    const response = await api.get(`/api/data-analysis/trajectory/${vehicleId.value}/`);
    mapData.trajectory = response.trajectory || [
      // 模拟轨迹数据 [经度, 纬度, 速度]
      [116.3972, 39.9096, 40], [116.4000, 39.9100, 50],
      [116.4050, 39.9120, 60], [116.4100, 39.9150, 30],
    ];

    if (map && mapData.trajectory.length > 0) {
      if (map.getSource('vehicle-trajectory')) {
        map.removeLayer('vehicle-trajectory');
        map.removeSource('vehicle-trajectory');
      }

      map.addSource('vehicle-trajectory', {
        type: 'geojson',
        data: {
          type: 'Feature',
          properties: {},
          geometry: {
            type: 'LineString',
            coordinates: []
          }
        }
      });

      map.addLayer({
        id: 'vehicle-trajectory',
        type: 'line',
        source: 'vehicle-trajectory',
        layout: {
          'line-join': 'round',
          'line-cap': 'round'
        },
        paint: {
          'line-color': ['interpolate', ['linear'], ['get', 'speed'], 0, 'blue', 50, 'green', 100, 'red'], // 根据速度变色
          'line-width': 4
        }
      });

      let path = [];
      let i = 0;
      const animate = () => {
        if (i < mapData.trajectory.length) {
          const [lng, lat, speed] = mapData.trajectory[i];
          path.push([lng, lat]);
          if (map.getSource('vehicle-trajectory')) {
            map.getSource('vehicle-trajectory').setData({
              type: 'Feature',
              properties: { speed: speed },
              geometry: {
                type: 'LineString',
                coordinates: path
              }
            });
          }
          map.setCenter([lng, lat]); // 地图中心跟随车辆移动
          i++;
          requestAnimationFrame(animate);
        } else {
          ElMessage.success('轨迹回放完成！');
        }
      };
      animate();
    } else {
      ElMessage.warning('未获取到车辆轨迹数据或地图未加载！');
    }
  } catch (error) {
    ElMessage.error('获取车辆轨迹失败！');
    console.error('Fetch trajectory error:', error);
  }
};
</script>

<style scoped>
.data-screen-container {
  padding: 10px;
  background-color: #0f1c30; /* 深色背景 */
  color: #eee;
  min-height: calc(100vh - 80px);
}
.data-screen-container h1 {
  text-align: center;
  color: #409eff;
  margin-bottom: 20px;
  font-size: 2em;
}
.dashboard-grid {
  height: calc(100vh - 150px); /* 占据大部分高度 */
}
.grid-col {
  height: 100%;
  display: flex;
  flex-direction: column;
  gap: 10px; /* 卡片之间的间距 */
}
.grid-card {
  background-color: #1a2a40; /* 卡片深色背景 */
  border: 1px solid #0f1c30;
  border-radius: 8px;
  color: #eee;
  flex-grow: 1; /* 占据可用空间 */
  height: calc(50% - 5px); /* 每列两个卡片，减去gap的一半 */
  box-shadow: 0 4px 10px rgba(0, 0, 0, 0.3);
}
.grid-card .card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 1.1em;
  font-weight: bold;
  color: #66b1ff;
  padding: 10px 15px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}
.chart-small {
  width: 100%;
  height: calc(100% - 40px); /* 减去header高度 */
  min-height: 200px;
}
.map-card {
  height: 100%;
}
#mapbox-container {
  width: 100%;
  height: calc(100% - 60px); /* 减去header高度 */
  min-height: 400px;
  background-color: #222;
}
</style>
