import { Nav } from "@/components/shell/Nav";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <>
      <Nav />
      <main className="mx-auto w-full max-w-[880px] px-4 py-6 sm:px-6 sm:py-8">{children}</main>
    </>
  );
}
