interface PaginationProps {
  page: number;
  total: number;
  pageSize: number;
  onChange: (page: number) => void;
}

export function Pagination({ page, total, pageSize, onChange }: PaginationProps) {
  const pages = Math.ceil(total / pageSize);
  if (pages <= 1) return null;
  const items: (number | '…')[] = [];
  for (let i = 1; i <= pages; i++) {
    if (i === 1 || i === pages || Math.abs(i - page) <= 1) items.push(i);
    else if (items[items.length - 1] !== '…') items.push('…');
  }
  return (
    <nav className="pagination-bar" aria-label="Pagination">
      <button
        type="button"
        className="page-btn"
        disabled={page === 1}
        aria-label="Previous page"
        onClick={() => onChange(page - 1)}
      >
        ‹
      </button>
      {items.map((item, i) =>
        item === '…'
          ? <span key={`e${i}`} className="page-ellipsis" aria-hidden="true">…</span>
          : (
            <button
              key={item}
              type="button"
              className={`page-btn${item === page ? ' active' : ''}`}
              aria-label={`Page ${item}`}
              aria-current={item === page ? 'page' : undefined}
              onClick={() => onChange(item as number)}
            >
              {item}
            </button>
          )
      )}
      <button
        type="button"
        className="page-btn"
        disabled={page === pages}
        aria-label="Next page"
        onClick={() => onChange(page + 1)}
      >
        ›
      </button>
    </nav>
  );
}
