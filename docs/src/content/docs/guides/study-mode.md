---
title: Study Mode
description: Configure focused study sessions for students
---

This guide helps students set up NextDNS Blocker for effective studying with minimal distractions.

## Overview

**Goal**: Create distraction-free study environment

**Strategy**:
- Block all social media during study hours
- Allow educational resources
- Scheduled breaks to prevent burnout
- Quick panic mode for exam periods

## Configuration

### Complete Example

```json
{
  "version": "1.0",
  "settings": {
    "timezone": "America/New_York",
    "editor": null
  },
  "blocklist": [
    {
      "domain": "reddit.com",
      "description": "Social media - study killer",
      "unblock_delay": "4h",
      "schedule": {
        "available_hours": [
          {
            "days": ["monday", "tuesday", "wednesday", "thursday", "friday"],
            "time_ranges": [
              {"start": "12:00", "end": "13:00"},
              {"start": "18:00", "end": "20:00"}
            ]
          },
          {
            "days": ["saturday", "sunday"],
            "time_ranges": [
              {"start": "12:00", "end": "22:00"}
            ]
          }
        ]
      }
    },
    {
      "domain": "twitter.com",
      "description": "Social media",
      "unblock_delay": "4h",
      "schedule": {
        "available_hours": [
          {
            "days": ["saturday", "sunday"],
            "time_ranges": [
              {"start": "14:00", "end": "20:00"}
            ]
          }
        ]
      }
    },
    {
      "domain": "instagram.com",
      "description": "Social media - high distraction",
      "unblock_delay": "4h",
      "schedule": {
        "available_hours": [
          {
            "days": ["saturday", "sunday"],
            "time_ranges": [
              {"start": "14:00", "end": "18:00"}
            ]
          }
        ]
      }
    },
    {
      "domain": "tiktok.com",
      "description": "Maximum time sink",
      "unblock_delay": "24h",
      "schedule": {
        "available_hours": [
          {
            "days": ["saturday"],
            "time_ranges": [
              {"start": "15:00", "end": "18:00"}
            ]
          }
        ]
      }
    },
    {
      "domain": "youtube.com",
      "description": "Video streaming - limited",
      "unblock_delay": "30m",
      "schedule": {
        "available_hours": [
          {
            "days": ["monday", "tuesday", "wednesday", "thursday", "friday"],
            "time_ranges": [
              {"start": "19:00", "end": "21:00"}
            ]
          },
          {
            "days": ["saturday", "sunday"],
            "time_ranges": [
              {"start": "10:00", "end": "22:00"}
            ]
          }
        ]
      }
    },
    {
      "domain": "netflix.com",
      "description": "Streaming - weekends",
      "unblock_delay": "4h",
      "schedule": {
        "available_hours": [
          {
            "days": ["friday"],
            "time_ranges": [
              {"start": "20:00", "end": "23:00"}
            ]
          },
          {
            "days": ["saturday", "sunday"],
            "time_ranges": [
              {"start": "14:00", "end": "22:00"}
            ]
          }
        ]
      }
    },
    {
      "domain": "discord.com",
      "description": "Chat - after study",
      "unblock_delay": "30m",
      "schedule": {
        "available_hours": [
          {
            "days": ["monday", "tuesday", "wednesday", "thursday", "friday"],
            "time_ranges": [
              {"start": "17:00", "end": "21:00"}
            ]
          },
          {
            "days": ["saturday", "sunday"],
            "time_ranges": [
              {"start": "10:00", "end": "22:00"}
            ]
          }
        ]
      }
    },
    {
      "domain": "twitch.tv",
      "description": "Game streaming",
      "unblock_delay": "4h",
      "schedule": {
        "available_hours": [
          {
            "days": ["saturday", "sunday"],
            "time_ranges": [
              {"start": "15:00", "end": "20:00"}
            ]
          }
        ]
      }
    }
  ],
  "allowlist": [
    {
      "domain": "wikipedia.org",
      "description": "Research"
    },
    {
      "domain": "khanacademy.org",
      "description": "Learning"
    },
    {
      "domain": "coursera.org",
      "description": "Courses"
    },
    {
      "domain": "edx.org",
      "description": "Courses"
    },
    {
      "domain": "quizlet.com",
      "description": "Flashcards"
    },
    {
      "domain": "wolframalpha.com",
      "description": "Math help"
    },
    {
      "domain": "docs.google.com",
      "description": "School work"
    },
    {
      "domain": "classroom.google.com",
      "description": "School"
    },
    {
      "domain": "canvas.instructure.com",
      "description": "School LMS"
    }
  ]
}
```

## Study Schedule Design

### Typical Weekday

```
06:00 ─────────────────────────────────────────────── 23:00
  │ MORNING │ SCHOOL │ STUDY │ BREAK │ STUDY │ FREE │
  │ BLOCKED │   ---  │BLOCKED│ALLOWED│BLOCKED│ALLOW │
  └─────────┴────────┴───────┴───────┴───────┴──────┘
    06-08     08-15    15-17   17-18   18-19   19-21
```

### Weekend

```
09:00 ─────────────────────────────────────────────── 23:00
  │ MORNING STUDY │    FREE TIME    │ EVENING │
  │    BLOCKED    │     ALLOWED     │  FREE   │
  └───────────────┴─────────────────┴─────────┘
       09-12           12-22           22-23
```

## Exam Mode

### During Exam Periods

Use panic mode for extended focus:

```bash
# 3-hour study session
nextdns-blocker panic 180

# Full day study
nextdns-blocker panic 8h

# Extend if needed
nextdns-blocker panic extend 60
```

### Pre-Exam Configuration

Temporarily increase restrictions:

```json
// Edit TikTok entry during exams
{
  "domain": "tiktok.com",
  "unblock_delay": "never",  // Change from "24h"
  "schedule": null           // Change to always blocked
}
```

Remember to revert after exams!

## Pomodoro Technique Integration

### 25-Minute Focus Sessions

For Pomodoro-style studying:

1. **Focus session**: Sites blocked
2. **5-min break**: Quick check allowed
3. **Repeat 4x**
4. **Long break**: Full access

### Quick Break Access

During short breaks, use pause:

```bash
# 5-minute break
nextdns-blocker pause 5
```

Sites unblock for 5 minutes, then auto-resume blocking.

## Subject-Specific Adjustments

### YouTube for Learning

If you use YouTube for educational content:

```json
{
  "domain": "youtube.com",
  "description": "Educational videos allowed",
  "unblock_delay": "0",  // Quick access for learning
  "schedule": {
    "available_hours": [
      // Include study hours
      {
        "days": ["monday", "tuesday", "wednesday", "thursday", "friday"],
        "time_ranges": [
          {"start": "15:00", "end": "17:00"},  // Study time
          {"start": "19:00", "end": "21:00"}   // Evening
        ]
      }
    ]
  }
}
```

### Reddit for Specific Subjects

Some subreddits are educational (r/learnpython, r/askscience):

```bash
# Temporary allowlist for research
nextdns-blocker allow reddit.com
# Remember to remove after
nextdns-blocker disallow reddit.com
```

## Building Study Habits

### Start Easy

Week 1-2: Light restrictions
```json
"unblock_delay": "0"
```

### Increase Gradually

Week 3-4: Add friction
```json
"unblock_delay": "30m"
```

### Full Commitment

Week 5+: Serious restrictions
```json
"unblock_delay": "4h"
```

## Group Study

### Scheduled Study Sessions

When studying with friends online:

```json
// Discord for group study
{
  "domain": "discord.com",
  "schedule": {
    "available_hours": [
      // Include study session times
      {
        "days": ["tuesday", "thursday"],
        "time_ranges": [
          {"start": "19:00", "end": "21:00"}
        ]
      }
    ]
  }
}
```

## Emergency Academic Access

### Need Blocked Site for Assignment

Options:

1. **Wait for scheduled time** (builds discipline)

2. **Use pause sparingly**:
   ```bash
   nextdns-blocker pause 30
   ```

3. **Add to allowlist temporarily**:
   ```bash
   nextdns-blocker allow specific-site.com
   # After done:
   nextdns-blocker disallow specific-site.com
   ```

## Tips for Success

### Environment Matters

Combine with:
- Physical phone out of reach
- Dedicated study space
- Background music/focus sounds

### Track Progress

Review weekly:
- How many times did you request unblocks?
- Which sites caused most temptation?
- Are study hours effective?

### Reward Yourself

Weekend access is your reward:
- Complete weekday study → enjoy weekend freedom
- Stay consistent → consider relaxing restrictions

### Accountability

Share with study buddy:
- Enable Discord notifications
- Check in on each other's progress
- Celebrate successful study weeks
