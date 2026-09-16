import { MobileShell } from "@/components/layout/MobileShell";
import { BottomNav } from "@/components/nav/BottomNav";
import { PageHeader } from "@/components/ui/PageHeader";

export default function FeedbackEmptyPage() {
  return (
    <MobileShell>
      <PageHeader backHref="/history/note" className="absolute left-0 top-[60px]" description="대화에서 받은 피드백을 확인해보세요." title="Feedback" variant="back" />
      <p className="absolute left-[5px] top-[399px] flex h-6 w-[362px] items-center justify-center text-body text-text-tertiary">아직 피드백이 없어요!</p>
      <BottomNav />
    </MobileShell>
  );
}
