/**
 * 解决SPA刷新404问题的工具文件
 * 在index.html中添加了此文件的引用
 */

// 检查是否处于开发环境
const isDev = import.meta.env.MODE === 'development';

// 检查当前URL是否是404页面
function checkIf404() {
  const currentUrl = window.location.href;
  // 如果是开发环境，检查URL中的路径
  if (isDev) {
    const routes = ['/dashboard', '/ai-monitor', '/alerts', '/reports', 
                    '/face-registration', '/data-screen', '/profile', '/users'];
    const currentPath = window.location.pathname;
    
    // 如果路径是有效的，但返回了404，刷新页面
    if (routes.some(route => currentPath.startsWith(route))) {
      // 当前是有效路由，如果页面状态是404，重定向到首页
      if (document.title.includes('404') || 
          document.body.textContent.includes('404') || 
          document.body.textContent.includes('Not Found')) {
        console.log('[SPA Router] 检测到404状态，重定向到应用首页');
        window.location.replace('/');
      }
    }
  }
}

// 页面加载后检查
window.addEventListener('load', checkIf404);

// 导出供路由使用
export function setupHistoryFallback(router) {
  router.onError((error) => {
    console.error('[Router Error]', error);
    // 如果是路由错误，重定向到首页
    window.location.replace('/');
  });
  
  return router;
} 