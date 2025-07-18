// 屏蔽浏览器控制台中过多的日志输出
// 将 VITE_SUPPRESS_CONSOLE 设为 'true' 时生效（.env 或环境变量）
(() => {
  // 默认在生产模式关闭；在开发模式可通过 VITE_SUPPRESS_CONSOLE 显式关闭
  const suppress = (import.meta.env.MODE === 'production') || (import.meta.env.VITE_SUPPRESS_CONSOLE === 'true');
  if (!suppress) return;

  const noop = () => {};
  ['log', 'debug', 'info'].forEach(method => {
    // 保留 console.error 与 console.warn
    try {
      console[method] = noop;
    } catch (e) {
      /* 忽略只读属性报错 */
    }
  });
})(); 