"use client";

import { BookOpen, CalendarDays, Home, ShoppingBasket, Sun, User, Users } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

const items = [
  { href: "/today", label: "Today", icon: Sun },
  { href: "/week", label: "Week", icon: CalendarDays },
  { href: "/pantry", label: "Pantry", icon: Home },
  { href: "/meals", label: "Meals", icon: BookOpen },
  { href: "/shopping", label: "Shopping", icon: ShoppingBasket },
  { href: "/household", label: "Household", icon: Users },
  { href: "/profile", label: "Profile", icon: User },
];

export function Nav() {
  const path = usePathname();
  return (
    <nav aria-label="Main" className="sticky top-0 z-30 border-b border-line bg-bg/95 backdrop-blur-sm">
      <div className="mx-auto flex max-w-[880px] items-center gap-1 overflow-x-auto px-4 py-2 sm:px-6">
        <Link href="/today" className="mr-3 font-display text-lg text-ink">
          Larder
        </Link>
        {items.map(({ href, label, icon: Icon }) => {
          const active = path === href || path.startsWith(href + "/");
          return (
            <Link
              key={href}
              href={href}
              aria-current={active ? "page" : undefined}
              className={`flex h-9 items-center gap-1.5 rounded-md px-2.5 text-sm ${
                active ? "bg-accent-soft text-ink" : "text-ink-muted hover:text-ink"
              }`}
            >
              <Icon size={18} strokeWidth={1.75} aria-hidden />
              <span className="hidden sm:inline">{label}</span>
            </Link>
          );
        })}
      </div>
    </nav>
  );
}
