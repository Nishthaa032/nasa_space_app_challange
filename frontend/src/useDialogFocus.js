import { useEffect, useRef } from "react";

// Keep keyboard navigation within the visible dialog and restore its trigger.
export default function useDialogFocus(open, onClose) {
  const closeRef = useRef(onClose);
  closeRef.current = onClose;
  useEffect(() => {
    if (!open) return;
    const previous = document.activeElement;
    const dialog = [...document.querySelectorAll('[role="dialog"]')].at(-1);
    if (!dialog) return;
    const focusable = () => [...dialog.querySelectorAll(
      'button:not(:disabled), a[href], input:not(:disabled), select:not(:disabled), [tabindex="0"]',
    )].filter((node) => node.getClientRects().length);
    const overflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    focusable()[0]?.focus();
    const handle = (event) => {
      if (event.key === "Escape") closeRef.current();
      if (event.key !== "Tab") return;
      const nodes = focusable();
      const first = nodes[0], last = nodes.at(-1);
      if (!first) { event.preventDefault(); return; }
      if (event.shiftKey && (document.activeElement === first || !dialog.contains(document.activeElement))) {
        event.preventDefault(); last.focus();
      } else if (!event.shiftKey && (document.activeElement === last || !dialog.contains(document.activeElement))) {
        event.preventDefault(); first.focus();
      }
    };
    document.addEventListener("keydown", handle);
    return () => {
      document.removeEventListener("keydown", handle);
      document.body.style.overflow = overflow;
      if (previous?.isConnected) previous.focus();
    };
  }, [open]);
}
