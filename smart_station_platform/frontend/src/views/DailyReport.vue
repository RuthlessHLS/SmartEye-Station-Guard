<template>
  <div class="daily-report-container">
    <h1>AI 自动监控日报</h1>
    <el-card class="filter-card">
      <el-form :inline="true" :model="reportFilterForm" class="filter-form">
        <el-form-item label="选择日期">
          <el-date-picker
            v-model="reportFilterForm.date"
            type="date"
            placeholder="选择日期"
            value-format="YYYY-MM-DD"
            @change="fetchReport"
          ></el-date-picker>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="fetchReport">查看报告</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card v-loading="loading" class="report-content-card">
      <template #header>
        <div class="card-header">
          <span>{{ report.date ? `${report.date} 监控日报` : '请选择日期' }}</span>
        </div>
      </template>
      <div v-if="report.summary">
        <h3 class="report-section-title">AI 摘要：</h3>
        <p class="report-summary">{{ report.summary }}</p>

        <h3 class="report-section-title">告警总数统计：</h3>
        <el-row :gutter="20">
          <el-col :span="8">
            <el-statistic title="告警总数" :value="report.totalAlerts"></el-statistic>
          </el-col>
          <el-col :span="8">
            <el-statistic title="已处理告警" :value="report.resolvedAlerts"></el-statistic>
          </el-col>
          <el-col :span="8">
            <el-statistic title="待处理告警" :value="report.pendingAlerts"></el-statistic>
          </el-col>
        </el-row>

        <el-row :gutter="20" style="margin-top: 20px;">
          <el-col :span="12">
            <h3 class="report-section-title">各类告警事件占比：</h3>
            <div id="alertTypeChart" class="chart"></div>
          </el-col>
          <el-col :span="12">
            <h3 class="report-section-title">24 小时告警趋势：</h3>
            <div id="alertTrendChart" class="chart"></div>
          </el-col>
        </el-row>

        <h3 class="report-section-title" style="margin-top: 30px;">关键告警事件：</h3>
        <el-row :gutter="20">
          <el-col :span="8" v-for="(event, index) in report.keyEvents" :key="index" style="margin-bottom: 20px;">
            <el-card :body-style="{ padding: '0px' }">
              <el-image
                :src="event.imageUrl"
                fit="contain"
                style="width: 100%; height: 200px;"
                lazy
              ></el-image>
              <div style="padding: 14px;">
                <span>{{ event.title }}</span>
                <div class="bottom card-header">
                  <time class="time">{{ event.time }}</time>
                </div>
              </div>
            </el-card>
          </el-col>
        </el-row>
      </div>
      <el-empty v-else description="暂无该日期报告数据，请选择其他日期或等待生成。"></el-empty>
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, nextTick } from 'vue';
import { ElMessage } from 'element-plus';
import api from '../api'; // 导入API请求服务
import * as echarts from 'echarts'; // 导入 ECharts

const loading = ref(false);
const reportFilterForm = reactive({
  date: new Date().toISOString().slice(0, 10), // 默认今天
});
const report = reactive({
  date: '',
  summary: '',
  totalAlerts: 0,
  resolvedAlerts: 0,
  pendingAlerts: 0,
  alertTypeDistribution: [], // [{ name: '类型1', value: 10 }, ...]
  alertTrend: [], // [{ hour: '00:00', count: 5 }, ...]
  keyEvents: [], // [{ title: '事件描述', time: '时间', imageUrl: 'URL' }, ...]
});

onMounted(() => {
  fetchReport(); // 页面加载时自动获取今天报告
});

const fetchReport = async () => {
  if (!reportFilterForm.date) {
    ElMessage.warning('请选择一个日期！');
    return;
  }
  loading.value = true;
  try {
    // 假设后端日报接口为 /api/reports/daily/
    const response = await api.get(`/reports/daily/${reportFilterForm.date}/`);
    if (response.data) {
      Object.assign(report, response.data); // 赋值报告数据
      report.date = reportFilterForm.date; // 确保日期显示正确
      // 等待DOM更新，然后初始化图表
      await nextTick();
      initCharts();
    } else {
      // 清空报告数据
      Object.assign(report, {
        date: reportFilterForm.date,
        summary: '',
        totalAlerts: 0,
        resolvedAlerts: 0,
        pendingAlerts: 0,
        alertTypeDistribution: [],
        alertTrend: [],
        keyEvents: [],
      });
    }
  } catch (error) {
    ElMessage.error('获取日报失败！');
    console.error('Fetch report error:', error);
    // 清空报告数据
    Object.assign(report, {
        date: reportFilterForm.date,
        summary: '',
        totalAlerts: 0,
        resolvedAlerts: 0,
        pendingAlerts: 0,
        alertTypeDistribution: [],
        alertTrend: [],
        keyEvents: [],
      });
  } finally {
    loading.value = false;
  }
};

const initCharts = () => {
  // 告警类型占比饼图
  const alertTypeChartDom = document.getElementById('alertTypeChart');
  if (alertTypeChartDom) {
    const alertTypeChart = echarts.init(alertTypeChartDom);
    const alertTypeOption = {
      tooltip: {
        trigger: 'item',
        formatter: '{a} <br/>{b} : {c} ({d}%)'
      },
      legend: {
        orient: 'vertical',
        left: 'left',
        data: report.alertTypeDistribution.map(item => item.name)
      },
      series: [
        {
          name: '告警类型',
          type: 'pie',
          radius: '55%',
          center: ['50%', '60%'],
          data: report.alertTypeDistribution,
          emphasis: {
            itemStyle: {
              shadowBlur: 10,
              shadowOffsetX: 0,
              shadowColor: 'rgba(0, 0, 0, 0.5)'
            }
          }
        }
      ]
    };
    alertTypeChart.setOption(alertTypeOption);
    window.addEventListener('resize', () => alertTypeChart.resize());
  }

  // 24 小时告警趋势折线图
  const alertTrendChartDom = document.getElementById('alertTrendChart');
  if (alertTrendChartDom) {
    const alertTrendChart = echarts.init(alertTrendChartDom);
    const alertTrendOption = {
      tooltip: {
        trigger: 'axis',
        axisPointer: {
          type: 'cross',
          label: {
            backgroundColor: '#6a7985'
          }
        }
      },
      grid: {
        left: '3%',
        right: '4%',
        bottom: '3%',
        containLabel: true
      },
      xAxis: {
        type: 'category',
        boundaryGap: false,
        data: report.alertTrend.map(item => item.hour)
      },
      yAxis: {
        type: 'value',
        minInterval: 1, // 确保Y轴刻度是整数
      },
      series: [
        {
          name: '告警数量',
          type: 'line',
          stack: '总量',
          areaStyle: {},
          emphasis: {
            focus: 'series'
          },
          data: report.alertTrend.map(item => item.count)
        }
      ]
    };
    alertTrendChart.setOption(alertTrendOption);
    window.addEventListener('resize', () => alertTrendChart.resize());
  }
};
</script>

<style scoped>
.daily-report-container {
  padding: 20px;
}
.daily-report-container h1 {
  text-align: center;
  margin-bottom: 20px;
}
.filter-card {
  margin-bottom: 20px;
}
.report-content-card {
  min-height: 600px;
}
.report-content-card .card-header {
  font-size: 1.2em;
  font-weight: bold;
  text-align: center;
}
.report-section-title {
  margin-top: 25px;
  margin-bottom: 15px;
  font-size: 1.1em;
  color: #303133;
  border-left: 4px solid #409eff;
  padding-left: 10px;
}
.report-summary {
  line-height: 1.8;
  color: #606266;
  text-align: left;
  margin-bottom: 20px;
}
.chart {
  width: 100%;
  height: 350px;
  margin: 20px 0;
  border: 1px solid #ebeef5;
  border-radius: 4px;
  background-color: #fff;
}
.el-statistic {
  text-align: center;
}
.time {
  font-size: 12px;
  color: #999;
}
</style>
