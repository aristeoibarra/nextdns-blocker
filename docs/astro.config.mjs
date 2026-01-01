// @ts-check
import starlight from "@astrojs/starlight";
import { defineConfig } from "astro/config";

// https://astro.build/config
export default defineConfig({
    integrations: [
        starlight({
            title: "NextDNS Blocker",

            social: [
                {
                    icon: "github",
                    label: "GitHub",
                    href: "https://github.com/aristeoibarra/nextdns-blocker",
                },
            ],
            editLink: {
                baseUrl:
                    "https://github.com/aristeoibarra/nextdns-blocker/edit/main/docs/",
            },

            customCss: ["./src/styles/custom.css"],
            sidebar: [
                {
                    label: "Getting Started",
                    items: [
                        { label: "Introduction", slug: "getting-started" },
                        {
                            label: "Why nextdns-blocker?",
                            slug: "why-nextdns-blocker",
                        },
                        {
                            label: "Installation",
                            slug: "getting-started/installation",
                        },
                        {
                            label: "Quick Setup",
                            slug: "getting-started/quick-setup",
                        },
                        {
                            label: "Your First Sync",
                            slug: "getting-started/first-sync",
                        },
                    ],
                },
                {
                    label: "Commands",
                    items: [
                        { label: "Overview", slug: "commands" },
                        { label: "sync", slug: "commands/sync" },
                        { label: "status", slug: "commands/status" },
                        {
                            label: "pause / resume",
                            slug: "commands/pause-resume",
                        },
                        { label: "unblock", slug: "commands/unblock" },
                        { label: "config", slug: "commands/config" },
                        { label: "watchdog", slug: "commands/watchdog" },
                        { label: "panic", slug: "commands/panic" },
                        { label: "pending", slug: "commands/pending" },
                        { label: "category", slug: "commands/category" },
                        {
                            label: "allow / disallow",
                            slug: "commands/allowlist",
                        },
                        { label: "update", slug: "commands/update" },
                    ],
                },
                {
                    label: "Configuration",
                    items: [
                        { label: "Overview", slug: "configuration" },
                        {
                            label: "Environment Variables",
                            slug: "configuration/env-variables",
                        },
                        {
                            label: "config.json Structure",
                            slug: "configuration/config-json",
                        },
                        { label: "Schedules", slug: "configuration/schedules" },
                        {
                            label: "Categories",
                            slug: "configuration/categories",
                        },
                        { label: "Blocklist", slug: "configuration/blocklist" },
                        { label: "Allowlist", slug: "configuration/allowlist" },
                        {
                            label: "Unblock Delay",
                            slug: "configuration/unblock-delay",
                        },
                        { label: "Timezone", slug: "configuration/timezone" },
                        {
                            label: "Filtering Priority",
                            slug: "configuration/filtering-priority",
                        },
                    ],
                },
                {
                    label: "Features",
                    items: [
                        { label: "Overview", slug: "features" },
                        { label: "Panic Mode", slug: "features/panic-mode" },
                        { label: "Watchdog", slug: "features/watchdog" },
                        {
                            label: "Pending Actions",
                            slug: "features/pending-actions",
                        },
                        {
                            label: "Discord Notifications",
                            slug: "features/notifications",
                        },
                        {
                            label: "Shell Completion",
                            slug: "features/shell-completion",
                        },
                        { label: "Dry Run Mode", slug: "features/dry-run" },
                    ],
                },
                {
                    label: "Guides",
                    items: [
                        { label: "Overview", slug: "guides" },
                        {
                            label: "Productivity Setup",
                            slug: "guides/productivity",
                        },
                        {
                            label: "Parental Control",
                            slug: "guides/parental-control",
                        },
                        { label: "Study Mode", slug: "guides/study-mode" },
                        {
                            label: "Gaming Schedule",
                            slug: "guides/gaming-schedule",
                        },
                        {
                            label: "Troubleshooting",
                            slug: "guides/troubleshooting",
                        },
                    ],
                },
                {
                    label: "Platforms",
                    items: [
                        { label: "Overview", slug: "platforms" },
                        { label: "macOS", slug: "platforms/macos" },
                        { label: "Linux", slug: "platforms/linux" },
                        { label: "Windows", slug: "platforms/windows" },
                        { label: "Docker", slug: "platforms/docker" },
                    ],
                },
                {
                    label: "Reference",
                    items: [
                        { label: "Overview", slug: "reference" },
                        {
                            label: "File Locations",
                            slug: "reference/file-locations",
                        },
                        { label: "Log Files", slug: "reference/log-files" },
                        { label: "Exit Codes", slug: "reference/exit-codes" },
                        { label: "Security", slug: "reference/security" },
                        {
                            label: "API & Rate Limiting",
                            slug: "reference/api-limits",
                        },
                    ],
                },
                {
                    label: "FAQ",
                    slug: "faq",
                },
            ],
        }),
    ],
});
