export function EmptyState({ title, body }: { title: string; body: string }) {
  return (
    <div className="border-2 border-dashed border-ink bg-[#fffaf0]/70 p-6">
      <h3 className="text-2xl font-black">{title}</h3>
      <p className="mt-2 max-w-xl text-sm font-semibold text-ink/70">{body}</p>
    </div>
  );
}

