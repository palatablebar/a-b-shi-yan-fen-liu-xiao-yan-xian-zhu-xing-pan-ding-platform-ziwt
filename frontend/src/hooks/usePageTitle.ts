/** 页面标题：记录本每页都有页眉，浏览器 tab 也跟随。 */
import { useEffect } from 'react';

export const usePageTitle = (title: string): void => {
  useEffect(() => {
    document.title = `${title} · abcheck 实验记录本`;
  }, [title]);
};
