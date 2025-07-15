import { ref, onUnmounted } from 'vue';
import axios from 'axios';

/**
 * WebRTC连接管理器，用于接收后端处理过的视频流
 * @param {String} apiBaseUrl - API基础URL，默认为http://localhost:8002
 * @returns {Object} - WebRTC连接管理API
 */
export default function useWebRTC(apiBaseUrl = import.meta.env.VITE_APP_AI_SERVICE_URL || 'http://127.0.0.1:8002') {
  const videoElement = ref(null);
  const isConnected = ref(false);
  const isConnecting = ref(false);
  const error = ref(null);
  const connectionId = ref(null);
  const peerConnection = ref(null);
  const shouldDisconnectAfterConnecting = ref(false); // 新增标志位
  const videoStreamActive = ref(false); // 新增：跟踪视频流是否活跃

  /**
   * 检查视频元素的可见性和状态
   * @private
   */
  const checkVideoElementStatus = () => {
    if (!videoElement.value) {
      console.error('[WebRTC] 视频元素不存在，无法检查状态');
      return false;
    }

    // 检查视频元素的CSS样式
    const styles = window.getComputedStyle(videoElement.value);
    const isVisible = styles.visibility !== 'hidden' && 
                     styles.display !== 'none' && 
                     parseFloat(styles.opacity) > 0;
    
    // 检查视频元素的大小
    const hasSize = videoElement.value.offsetWidth > 0 && 
                   videoElement.value.offsetHeight > 0;
    
    // 检查视频流状态
    const hasStream = !!videoElement.value.srcObject;
    
    console.log('[WebRTC] 视频元素状态检查:', 
      'isVisible:', isVisible,
      'hasSize:', hasSize,
      'hasStream:', hasStream,
      'width:', videoElement.value.offsetWidth,
      'height:', videoElement.value.offsetHeight,
      'readyState:', videoElement.value.readyState
    );
    
    // 如果视频元素存在问题，尝试修复
    if (!isVisible || !hasSize) {
      console.warn('[WebRTC] 视频元素可能不可见，尝试修复样式');
      videoElement.value.style.display = 'block';
      videoElement.value.style.visibility = 'visible';
      videoElement.value.style.width = '100%';
      videoElement.value.style.height = '100%';
      videoElement.value.style.opacity = '1';
      videoElement.value.style.position = 'absolute';
      videoElement.value.style.top = '0';
      videoElement.value.style.left = '0';
      videoElement.value.style.zIndex = '10';
    }
    
    return isVisible && hasSize && hasStream;
  };

  /**
   * 连接到指定摄像头的WebRTC流
   * @param {String} cameraId - 摄像头ID
   * @param {HTMLVideoElement} videoEl - 视频元素引用
   */
  const connect = async (cameraId, videoEl) => {
    if (isConnecting.value) {
      console.warn('[WebRTC] 已经在连接中，请等待连接完成');
      return;
    }
    
    if (isConnected.value) {
      console.info('[WebRTC] 已连接，正在重新连接...');
      await disconnect();
    }

    if (!videoEl) {
      console.error('[WebRTC] 视频元素未提供，无法连接WebRTC');
      throw new Error('WebRTC连接失败：视频元素未定义');
    }

    // 先检查视频元素的状态
    console.log('[WebRTC] 视频元素初始状态:', 
      'offsetWidth:', videoEl.offsetWidth,
      'offsetHeight:', videoEl.offsetHeight,
      'style.display:', videoEl.style.display,
      'style.visibility:', videoEl.style.visibility
    );

    videoElement.value = videoEl;
    isConnecting.value = true;
    error.value = null;
    shouldDisconnectAfterConnecting.value = false; // 重置标志
    videoStreamActive.value = false; // 重置视频流状态

    try {
      console.log(`[WebRTC] 正在连接到 ${apiBaseUrl}/webrtc/offer/${cameraId}`);
      
      // 创建RTCPeerConnection
      const pc = new RTCPeerConnection({
        iceServers: [{ urls: 'stun:stun.l.google.com:19302' }]
      });
      peerConnection.value = pc;

      // 设置事件处理程序
      pc.ontrack = (event) => {
        if (videoElement.value) {
          console.log('[WebRTC] 接收到WebRTC流，附加到视频元素');
          
          // 记录流信息
          const stream = event.streams[0];
          console.log('[WebRTC] 流信息:', 
            'ID:', stream.id,
            '轨道数量:', stream.getTracks().length,
            '视频轨道:', stream.getVideoTracks().length > 0 ? '有' : '无',
            '音频轨道:', stream.getAudioTracks().length > 0 ? '有' : '无'
          );
          
          // 如果已有srcObject，先清除
          if (videoElement.value.srcObject) {
            console.log('[WebRTC] 移除现有视频流');
            const oldTracks = videoElement.value.srcObject.getTracks();
            oldTracks.forEach(track => track.stop());
            videoElement.value.srcObject = null;
          }
          
          // 设置新流
          videoElement.value.srcObject = stream;
          
          // 【增强】确保视频元素可见
          videoElement.value.style.display = 'block';
          videoElement.value.style.visibility = 'visible';
          videoElement.value.style.width = '100%';
          videoElement.value.style.height = '100%';
          videoElement.value.style.position = 'absolute';
          videoElement.value.style.top = '0';
          videoElement.value.style.left = '0';
          videoElement.value.style.zIndex = '10';
          
          // 监听视频轨道状态
          stream.getVideoTracks().forEach(track => {
            console.log('[WebRTC] 视频轨道状态:', track.label, track.enabled, track.readyState);
            
            track.onended = () => {
              console.log('[WebRTC] 视频轨道已结束:', track.label);
              videoStreamActive.value = false;
            };
            
            track.onmute = () => {
              console.log('[WebRTC] 视频轨道已静音:', track.label);
            };
            
            track.onunmute = () => {
              console.log('[WebRTC] 视频轨道已取消静音:', track.label);
              videoStreamActive.value = true;
            };
          });
          
          // 尝试播放视频
          videoElement.value.play()
            .then(() => {
              console.log('[WebRTC] 视频播放成功');
              videoStreamActive.value = true;
            })
            .catch(err => {
              console.error('[WebRTC] 视频播放失败:', err);
              
              // 【增强】尝试自动恢复播放
              const autoRecovery = () => {
                if (!videoStreamActive.value && videoElement.value && videoElement.value.paused) {
                  console.log('[WebRTC] 尝试自动恢复视频播放');
                  videoElement.value.play()
                    .then(() => {
                      console.log('[WebRTC] 自动恢复视频播放成功');
                      videoStreamActive.value = true;
                    })
                    .catch(recErr => {
                      console.error('[WebRTC] 自动恢复视频播放失败:', recErr);
                    });
                }
              };
              
              // 每3秒尝试恢复播放，直到成功
              const recoveryInterval = setInterval(() => {
                if (videoStreamActive.value || !isConnected.value) {
                  clearInterval(recoveryInterval);
                } else {
                  autoRecovery();
                }
              }, 3000);
            });
            
            // 检查视频元素状态
            checkVideoElementStatus();
        } else {
          console.error('[WebRTC] 收到流，但视频元素不存在！');
        }
      };

      pc.onicecandidate = (event) => {
        if (event.candidate) {
          console.log('[WebRTC] ICE候选: ', event.candidate);
        }
      };

      pc.oniceconnectionstatechange = () => {
        console.log('[WebRTC] ICE连接状态: ', pc.iceConnectionState);
        if (pc.iceConnectionState === 'connected' || pc.iceConnectionState === 'completed') {
          isConnected.value = true;
          isConnecting.value = false;
          if (videoElement.value && videoElement.value.srcObject) {
            console.log('[WebRTC] WebRTC连接已建立，视频流已就绪');
            
            // 尝试强制播放
            videoElement.value.play()
              .then(() => {
                console.log('[WebRTC] ICE连接后视频播放成功');
                videoStreamActive.value = true;
              })
              .catch(err => console.error('[WebRTC] ICE连接后视频播放失败:', err));
              
            // 检查视频元素状态
            setTimeout(() => {
              if (videoElement.value) {
                console.log('[WebRTC] 2秒后视频元素状态:', 
                  'readyState:', videoElement.value.readyState,
                  'paused:', videoElement.value.paused,
                  'videoWidth:', videoElement.value.videoWidth,
                  'videoHeight:', videoElement.value.videoHeight
                );
                
                // 再次检查视频元素可见性
                checkVideoElementStatus();
              }
            }, 2000);
          } else {
            console.warn('[WebRTC] WebRTC连接已建立，但视频流未就绪');
          }
        } else if (pc.iceConnectionState === 'failed' || pc.iceConnectionState === 'disconnected' || pc.iceConnectionState === 'closed') {
          isConnected.value = false;
          isConnecting.value = false;
          videoStreamActive.value = false;
          console.error(`[WebRTC] ICE连接状态变为 ${pc.iceConnectionState}`);
        }
      };

      // 从后端获取offer
      const response = await axios.post(`${apiBaseUrl}/webrtc/offer/${cameraId}`);
      const { sdp, type, connection_id } = response.data;
      connectionId.value = connection_id;

      console.log(`[WebRTC] 收到offer，连接ID: ${connection_id}`);

      // 设置远程描述（服务器的offer）
      try {
        await pc.setRemoteDescription({ type, sdp });
        console.log('[WebRTC] 远程描述设置成功');
      } catch (e) {
        console.error('[WebRTC] 设置远程描述失败:', e);
        throw e;
      }

      // 创建应答
      let answer;
      try {
        answer = await pc.createAnswer();
        await pc.setLocalDescription(answer);
        console.log('[WebRTC] 本地描述设置成功');
      } catch (e) {
        console.error('[WebRTC] 创建或设置本地描述失败:', e);
        throw e;
      }

      console.log(`[WebRTC] 发送answer到 ${apiBaseUrl}/webrtc/answer/${connection_id}`);
      
      // 将应答发送到服务器
      try {
        await axios.post(`${apiBaseUrl}/webrtc/answer/${connection_id}`, {
          sdp: answer.sdp,
          type: answer.type
        });
        console.log('[WebRTC] 发送answer成功');
      } catch (e) {
        console.error('[WebRTC] 发送answer失败:', e);
        throw e;
      }

      console.log('[WebRTC] WebRTC连接已建立，连接ID: ', connection_id);

      // 添加10秒超时检查，如果没有收到视频流，报告错误
      setTimeout(() => {
        if (isConnected.value && videoElement.value) {
          if (!videoElement.value.srcObject) {
            console.error('[WebRTC] 连接超时：已连接但未收到视频流');
            error.value = '连接超时：已连接但未收到视频流';
          } else {
            console.log('[WebRTC] 10秒检查：视频状态', 
              'readyState:', videoElement.value.readyState,
              'paused:', videoElement.value.paused,
              'videoWidth:', videoElement.value.videoWidth,
              'videoHeight:', videoElement.value.videoHeight
            );
            
            // 检查视频是否真的在播放
            if (videoElement.value.paused || videoElement.value.ended) {
              console.warn('[WebRTC] 10秒检查：视频处于暂停或结束状态，尝试重新播放');
              videoElement.value.play()
                .then(() => console.log('[WebRTC] 重新播放成功'))
                .catch(err => console.error('[WebRTC] 重新播放失败:', err));
            }
            
            // 再次检查视频元素可见性
            checkVideoElementStatus();
          }
        }
      }, 10000);
      
    } catch (err) {
      console.error('[WebRTC] 连接错误: ', err);
      error.value = err.message || '连接失败';
      isConnected.value = false;
      isConnecting.value = false;
      videoStreamActive.value = false;
      disconnect(); // 出错时也调用disconnect来清理
      throw new Error(`WebRTC连接失败: ${err.message}`);
    } finally {
      isConnecting.value = false; // 确保在结束时重置
      // 如果在连接过程中收到了断开请求，则在这里执行
      if (shouldDisconnectAfterConnecting.value) {
        console.log('[WebRTC] 连接已完成，现在执行延迟的断开操作。');
        disconnect();
      }
    }
  };

  /**
   * 断开WebRTC连接
   */
  const disconnect = async () => {
    // 【修复】如果正在连接中，则延迟断开操作
    if (isConnecting.value) {
      console.warn('[WebRTC] 正在连接时请求断开，将延迟到连接完成后处理。');
      shouldDisconnectAfterConnecting.value = true;
      return;
    }

    if (peerConnection.value) {
      peerConnection.value.close();
      peerConnection.value = null;
      console.log('[WebRTC] 已关闭对等连接');
    }

    if (videoElement.value && videoElement.value.srcObject) {
      const tracks = videoElement.value.srcObject.getTracks();
      tracks.forEach(track => track.stop());
      videoElement.value.srcObject = null;
      console.log('[WebRTC] 已停止视频轨道');
    }

    if (connectionId.value) {
      try {
        await axios.delete(`${apiBaseUrl}/webrtc/connection/${connectionId.value}`);
        console.log('[WebRTC] 已通知服务器关闭连接: ', connectionId.value);
      } catch (err) {
        console.error('[WebRTC] 关闭WebRTC连接时出错: ', err);
      }
      connectionId.value = null;
    }

    isConnected.value = false;
    videoStreamActive.value = false;
  };

  // 连接状态检查
  const checkConnection = () => {
    // 检查WebRTC连接状态
    const peerConnectionStatus = peerConnection.value?.iceConnectionState || 'closed';
    
    // 检查视频元素状态
    const videoStatus = videoElement.value ? {
      paused: videoElement.value.paused,
      ended: videoElement.value.ended,
      readyState: videoElement.value.readyState,
      hasStream: !!videoElement.value.srcObject,
      trackCount: videoElement.value.srcObject?.getTracks().length || 0
    } : null;
    
    // 检查视频元素可见性
    const videoVisibility = checkVideoElementStatus();
    
    console.log('[WebRTC] 连接状态检查:', 
      'isConnected:', isConnected.value,
      'videoStreamActive:', videoStreamActive.value,
      'peerConnectionStatus:', peerConnectionStatus,
      'videoStatus:', videoStatus,
      'videoVisibility:', videoVisibility
    );
    
    return {
      isConnected: isConnected.value,
      isVideoActive: videoStreamActive.value,
      peerConnectionStatus,
      videoStatus,
      videoVisibility
    };
  };

  // 在组件卸载时自动断开连接
  onUnmounted(() => {
    if (isConnected.value) {
      disconnect();
    }
  });

  return {
    connect,
    disconnect,
    isConnected,
    videoStreamActive,
    error,
    checkConnection
  };
} 