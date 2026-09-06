export default function PasswordStrength({ password }: { password: string }) {
  if (!password) return null;
  let score = 0;
  if (password.length >= 8) score += 1;
  if (password.length >= 12) score += 1;
  if (/[a-z]/.test(password) && /[A-Z]/.test(password)) score += 1;
  if (/\d/.test(password) && /[^a-zA-Z0-9]/.test(password)) score += 1;
  const labels = ["Too weak", "Weak", "Fair", "Good", "Strong"];
  const colors = ["bg-red-400", "bg-orange-400", "bg-amber-400", "bg-lime-500", "bg-emerald-500"];
  return (
    <div className="mt-1.5 flex items-center gap-2" aria-label={`Password strength: ${labels[score]}`}>
      <div className="flex h-1 flex-1 gap-1">
        {[0, 1, 2, 3].map((i) => (
          <div
            key={i}
            className={`h-full flex-1 rounded-full ${i < score ? colors[score] : "bg-slate-200"}`}
          />
        ))}
      </div>
      <span className="text-[11px] font-medium text-slate-500">{labels[score]}</span>
    </div>
  );
}
