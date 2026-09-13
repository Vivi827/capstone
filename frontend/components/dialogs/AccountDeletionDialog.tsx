"use client";

import { useState } from "react";

import { PopupActionButton } from "@/components/ui/PopupActionButton";

type AccountDeletionDialogProps = {
  isDeleting: boolean;
  onCancel: () => void;
  onConfirm: () => void;
};

export function AccountDeletionDialog({ isDeleting, onCancel, onConfirm }: AccountDeletionDialogProps) {
  const [confirmation, setConfirmation] = useState("");

  return (
    <div className="absolute inset-0 z-40 bg-black/60">
      <section
        aria-labelledby="account-deletion-title"
        aria-describedby="account-deletion-description"
        aria-modal="true"
        aria-busy={isDeleting}
        className="absolute left-5 top-1/2 w-[calc(100%-40px)] -translate-y-1/2 rounded-3xl bg-white p-6 shadow-[0_24px_56px_rgba(28,26,23,0.14)]"
        role="dialog"
      >
        <h2 className="text-title-2 text-text" id="account-deletion-title">정말 탈퇴할까요?</h2>
        <p className="mt-3 text-body-2 text-text-secondary" id="account-deletion-description">
          계정과 모든 대화·학습 기록이 즉시 삭제돼요. 삭제한 기록은 복구할 수 없으며, 다시 가입하면 처음부터 시작해요.
        </p>
        <label className="mt-5 block text-caption-1 text-text-secondary" htmlFor="account-deletion-confirmation">
          계속하려면 아래에 ‘회원탈퇴’를 입력해 주세요.
        </label>
        <input
          autoComplete="off"
          className="mt-2 h-11 w-full rounded-xl border border-[#e4dfd5] px-3 text-body text-text focus:border-primary focus:outline-none"
          disabled={isDeleting}
          id="account-deletion-confirmation"
          onChange={(event) => setConfirmation(event.target.value)}
          value={confirmation}
        />
        <div className="mt-6 flex justify-end gap-3">
          <PopupActionButton disabled={isDeleting} onClick={onCancel}>돌아가기</PopupActionButton>
          <PopupActionButton disabled={isDeleting || confirmation !== "회원탈퇴"} onClick={onConfirm} variant="primary">
            {isDeleting ? "탈퇴 처리 중..." : "회원탈퇴"}
          </PopupActionButton>
        </div>
      </section>
    </div>
  );
}
