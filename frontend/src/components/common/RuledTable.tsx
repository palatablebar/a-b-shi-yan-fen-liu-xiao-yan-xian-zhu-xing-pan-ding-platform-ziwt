/** 横格表：统一表头/行样式，支持行级批注标记。 */
import type { ReactNode } from 'react';

export interface Column<T> {
  key: string;
  label: string;
  align?: 'left' | 'right' | 'center';
  width?: string;
  render: (row: T, index: number) => ReactNode;
}

interface RuledTableProps<T> {
  columns: Column<T>[];
  rows: T[];
  rowKey: (row: T, index: number) => string | number;
  flagged?: (row: T) => boolean;
  empty?: ReactNode;
}

export const RuledTable = <T,>({
  columns,
  rows,
  rowKey,
  flagged,
  empty,
}: RuledTableProps<T>) => {
  if (rows.length === 0) {
    return <div className="empty">{empty ?? <p>暂无数据。</p>}</div>;
  }
  return (
    <div style={{ overflowX: 'auto' }}>
      <table className="ruled">
        <thead>
          <tr>
            {columns.map((column) => (
              <th
                key={column.key}
                style={{ width: column.width, textAlign: column.align ?? 'left' }}
              >
                {column.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, index) => (
            <tr
              key={rowKey(row, index)}
              className={flagged?.(row) ? 'flagged' : undefined}
            >
              {columns.map((column) => (
                <td
                  key={column.key}
                  className={column.align === 'right' ? 'num' : column.align === 'center' ? 'center' : ''}
                >
                  {column.render(row, index)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};
