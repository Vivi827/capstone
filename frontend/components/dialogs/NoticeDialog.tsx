"use client";

import { useEffect, useId, useRef } from "react";

import { PopupActionButton } from "@/components/ui/PopupActionButton";

type NoticeDialogProps = {
  body: string;
  onConfirm: () => void;
  title: string;
};

export function NoticeDialog({ body, onConfirm, title }: NoticeDialogProps) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const titleId = useId();
  const bodyId = useId();

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;
    dialog.showModal();
    return () => dialog.close();
  }, []);

  return (
    <dialog
      aria-describedby={bodyId}
      aria-labelledby={titleId}
      className="fixed inset-0 m-auto w-[calc(100%-40px)] max-w-[362px] rounded-3xl border-0 bg-white p-6 text-text shadow-[0_24px_56px_rgba(28,26,23,0.14)] backdrop:bg-black/60"
      onCancel={(event) => {
        event.preventDefault();
        onConfirm();
      }}
      onKeyDown={(event) => {
        if (event.key === "Tab") {
          event.preventDefault();
          event.currentTarget.querySelector("button")?.focus();
        }
      }}
      ref={dialogRef}
    >
      <h2 className="text-title-2" id={titleId}>{title}</h2>
      <p className="mt-2 whitespace-pre-line text-body-2 text-text-secondary" id={bodyId}>{body}</p>
      <div className="mt-6 flex justify-end">
        <PopupActionButton onClick={onConfirm} variant="primary">확인</PopupActionButton>
      </div>
    </dialog>
  );
}
