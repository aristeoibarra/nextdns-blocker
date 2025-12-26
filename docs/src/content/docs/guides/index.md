---
title: Guides Overview
description: Practical guides for common use cases
---

These guides provide step-by-step instructions for setting up NextDNS Blocker for specific scenarios.

## Available Guides

### [Productivity Setup](/guides/productivity/)

Optimize your work environment by blocking distractions during focus hours while allowing access during breaks.

**Best for**: Remote workers, office professionals, freelancers

### [Parental Control](/guides/parental-control/)

Set up protected blocking for children with restricted hours and maximum friction against circumvention.

**Best for**: Parents, guardians, families

### [Study Mode](/guides/study-mode/)

Configure focused study sessions with educational exceptions and strict social media controls.

**Best for**: Students, learners, exam preparation

### [Gaming Schedule](/guides/gaming-schedule/)

Manage gaming platform access with reasonable evening and weekend hours.

**Best for**: Gamers managing time, parents of gamers

### [Troubleshooting](/guides/troubleshooting/)

Diagnose and fix common issues with NextDNS Blocker.

**For everyone**: When things don't work as expected

## Choosing a Guide

| Your Goal | Recommended Guide |
|-----------|-------------------|
| Focus during work | [Productivity](/guides/productivity/) |
| Protect children | [Parental Control](/guides/parental-control/) |
| Better study habits | [Study Mode](/guides/study-mode/) |
| Manage gaming time | [Gaming Schedule](/guides/gaming-schedule/) |
| Fix issues | [Troubleshooting](/guides/troubleshooting/) |

## Combining Configurations

Guides can be combined. For example:
- Productivity + Gaming = Work focus with controlled gaming
- Study Mode + Parental Control = Student with extra protection

## Pre-Built Templates

Each guide references templates in the `examples/` directory:

```bash
# View available templates
ls examples/

# Copy a template
cp examples/work-focus.json ~/.config/nextdns-blocker/config.json

# Customize
nextdns-blocker config edit
```

## Contributing Guides

Have a setup that works well? Contributions welcome:
1. Document your configuration
2. Explain the reasoning
3. Submit a pull request

See [CONTRIBUTING.md](https://github.com/aristeoibarra/nextdns-blocker/blob/main/CONTRIBUTING.md) for guidelines.
