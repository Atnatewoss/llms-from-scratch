import type * as React from "react";
import Link from "next/link";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarHeader,
  SidebarRail,
  SidebarTrigger,
} from "@/components/ui/sidebar";
import { ThreadList } from "@/components/assistant-ui/elements/thread-list.aui";

const SITE_NAME = "LLMs from Scratch";

/** Same mark as app/favicon.ico, inlined so it stays crisp at 16px. */
const SiteIcon = (props: React.SVGProps<SVGSVGElement>) => (
  <svg viewBox="0 0 64 64" aria-hidden {...props}>
    <rect width="64" height="64" rx="14" fill="#111111" />
    <path
      d="M46.7 40.5A17 17 0 1 1 40.5 17.3"
      fill="none"
      stroke="#f2f2f2"
      strokeWidth="6"
      strokeLinecap="round"
    />
    <circle cx="32" cy="32" r="5" fill="#f2f2f2" />
  </svg>
);

// Placeholder account until auth is wired up.
const user = { name: "Alex Nguyen" };
const initials = user.name
  .split(" ")
  .map((part) => part[0])
  .join("")
  .toUpperCase();

export function ThreadListSidebar({
  ...props
}: React.ComponentProps<typeof Sidebar>) {
  return (
    <Sidebar collapsible="icon" {...props}>
      <SidebarHeader className="aui-sidebar-header">
        <div className="flex items-center justify-between gap-1 group-data-[collapsible=icon]:justify-center">
          <Link
            href="/"
            className="aui-sidebar-brand flex min-w-0 items-center gap-2 rounded-md p-1 group-data-[collapsible=icon]:hidden"
          >
            <SiteIcon className="size-5 shrink-0" />
            <span className="truncate text-sm font-semibold">{SITE_NAME}</span>
          </Link>
          <SidebarTrigger />
        </div>
      </SidebarHeader>
      <SidebarContent className="aui-sidebar-content px-2 pb-2">
        <ThreadList />
      </SidebarContent>
      {props.collapsible !== "none" && <SidebarRail />}
      {/* Threads scroll under this blurred fade into the account row. */}
      <div
        aria-hidden
        className="relative z-10 -mt-12 h-12 shrink-0 pointer-events-none bg-[linear-gradient(to_top,var(--sidebar),transparent)] backdrop-blur-[3px] group-data-[collapsible=icon]:hidden"
      />
      <SidebarFooter className="aui-sidebar-footer p-2 pt-1">
        <div className="flex items-center gap-2 rounded-lg px-2 py-1.5 group-data-[collapsible=icon]:justify-center group-data-[collapsible=icon]:px-0">
          <Avatar size="sm">
            <AvatarFallback>{initials}</AvatarFallback>
          </Avatar>
          <div className="grid min-w-0 flex-1 leading-tight group-data-[collapsible=icon]:hidden">
            <span className="truncate text-sm font-medium">{user.name}</span>
          </div>
        </div>
      </SidebarFooter>
    </Sidebar>
  );
}
