import { useEffect, useRef, useState } from "react";

export default function AccountMenu({ page, onNavigate, onLogout }) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef(null);

  useEffect(() => {
    function onPointerDown(event) {
      if (rootRef.current && !rootRef.current.contains(event.target)) {
        setOpen(false);
      }
    }
    document.addEventListener("pointerdown", onPointerDown);
    return () => document.removeEventListener("pointerdown", onPointerDown);
  }, []);

  function go(next) {
    onNavigate(next);
    setOpen(false);
  }

  return (
    <div className="menu" ref={rootRef}>
      <button
        type="button"
        className="ghost menu-trigger"
        aria-expanded={open}
        aria-haspopup="menu"
        onClick={() => setOpen((value) => !value)}
      >
        Menu
      </button>
      {open ? (
        <div className="menu-panel" role="menu">
          <button
            type="button"
            role="menuitem"
            className={page === "upload" ? "menu-item current" : "menu-item"}
            onClick={() => go("upload")}
          >
            Upload
          </button>
          <button
            type="button"
            role="menuitem"
            className={page === "download" ? "menu-item current" : "menu-item"}
            onClick={() => go("download")}
          >
            Download
          </button>
          <button
            type="button"
            role="menuitem"
            className="menu-item danger-item"
            onClick={() => {
              setOpen(false);
              onLogout();
            }}
          >
            Log out
          </button>
        </div>
      ) : null}
    </div>
  );
}
