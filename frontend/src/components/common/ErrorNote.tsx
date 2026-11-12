/** 可恢复错误态：展示原因 + 重试按钮。 */
interface ErrorNoteProps {
  message: string;
  onRetry?: () => void;
}

export const ErrorNote = ({ message, onRetry }: ErrorNoteProps) => (
  <div className="empty" role="alert">
    <h4>读取失败</h4>
    <p>{message}</p>
    {onRetry ? (
      <div style={{ marginTop: 12 }}>
        <button className="btn small" onClick={onRetry}>
          重新加载
        </button>
      </div>
    ) : null}
  </div>
);
