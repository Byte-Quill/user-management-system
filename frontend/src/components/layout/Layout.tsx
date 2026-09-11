import AppShell from "@/components/layout/AppShell";
import { ConfirmDialogProvider } from "@/components/ui/ConfirmDialog";
import { ToastProvider } from "@/components/ui/Toast";

export const ROLE_LABELS: Record<string, string> = {
  applicant: "Applicant",
  admin: "Admin",
  super_admin: "Super Admin",
  ceo: "CEO",
};

export default function Layout() {
  return (
    <ToastProvider>
      <ConfirmDialogProvider>
        <AppShell />
      </ConfirmDialogProvider>
    </ToastProvider>
  );
}
