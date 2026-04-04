import { useState } from "react";

interface Props {
  title: string;
  children: React.ReactNode;
}

/**
 * 「?」アイコン → クリックで概念説明をポップオーバー表示
 */
export default function InfoPopover({ title, children }: Props) {
  const [open, setOpen] = useState(false);

  return (
    <span className="relative inline-block ml-1">
      <button
        onClick={() => setOpen(!open)}
        className="w-5 h-5 rounded-full bg-blue-100 text-blue-600 text-xs font-bold
                   hover:bg-blue-200 transition-colors inline-flex items-center justify-center"
        aria-label={`${title}の説明`}
      >
        ?
      </button>
      {open && (
        <>
          <div className="fixed inset-0 z-40" onClick={() => setOpen(false)} />
          <div className="absolute z-50 left-6 top-0 w-72 bg-white border border-gray-200
                          rounded-lg shadow-lg p-4 text-sm text-gray-700">
            <div className="font-semibold text-gray-900 mb-2">{title}</div>
            {children}
          </div>
        </>
      )}
    </span>
  );
}
