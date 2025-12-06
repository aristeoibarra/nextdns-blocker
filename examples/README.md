# Example Configs

This folder contains ready-to-use JSON examples demonstrating common scheduling patterns and protection settings for domains.

How schedules work
- **`available_hours`**: lists when a domain is allowed. Outside these windows the domain is blocked.
- **Days**: use lowercase names (`monday`, `tuesday`, ..., `sunday`).
- **Times**: 24-hour `HH:MM` format.

Files

- `minimal.json`: Minimal, versatile examples meant for quick customization:
	- `example-site.com` — demonstrates a time-limited access pattern (weekdays evenings, full weekends).
	- `always-blocked.com` — no `schedule` field (always blocked).
	- `weekends-only.com` — accessible only on weekends.
	- `business-hours-only.com` — accessible only Mon–Fri 09:00–17:00.
	- `morning-block.com` — blocked until 11:00, then available the rest of the day.
	Tip: copy the entry you like and edit `days`/`time_ranges` to create your own rules.

- `work-focus.json`: A focused example that combines social and gaming domains and applies a "work hours" policy.
	- Intended to limit distractions during work: domains are typically only available after work hours and on weekends.
	- Good starting point for teams or individuals who want a single profile that covers multiple distraction categories.

- `gaming.json`: Gaming-related domains (stores/platforms).
	- Default schedule: available mostly on weekends and late evenings on weekdays (e.g. 20:00+).
	- Use this file to block game stores and platforms during daytime/work hours.

- `social-media.json`: Popular social networks and forums.
	- Default schedule: restricted during weekdays (evenings-only) and available on weekends.
	- Adjust the weekday `time_ranges` to tighten or loosen access.

- `parental-content.json`: Examples for stricter parental controls.
	- Contains adult/gambling domains.
	- Domains are marked with `"protected": true` and have no schedule (always blocked).
	- `protected: true` prevents these domains from being unblocked via the CLI — useful for enforcing policies.

Quick tips
- To make a domain always blocked, omit the `schedule` field or set `"schedule": null`.
- To allow a domain only during specific windows, set `available_hours` with `days` and `time_ranges`.
- To prevent users from unblocking a domain via the CLI, set `"protected": true`.

Need help customizing these? Tell us which pattern you want (e.g. "block social sites during work hours, allow evenings") and we can provide a ready-to-use example.

**Schedule Snippets**
- `Block during work hours` : allow evenings and weekends, block daytime work hours.

```json
{
	"domain": "example.com",
	"description": "Block during work hours, allow evenings and weekends",
	"protected": false,
	"schedule": {
		"available_hours": [
			{
				"days": ["saturday", "sunday"],
				"time_ranges": [{"start": "00:00", "end": "23:59"}]
			},
			{
				"days": ["monday", "tuesday", "wednesday", "thursday", "friday"],
				"time_ranges": [{"start": "18:00", "end": "23:59"}]
			}
		]
	}
}
```

- `Allow only business hours` : accessible only Mon–Fri 09:00–17:00.

```json
{
	"domain": "intranet.example",
	"description": "Accessible only during business hours",
	"protected": false,
	"schedule": {
		"available_hours": [
			{
				"days": ["monday", "tuesday", "wednesday", "thursday", "friday"],
				"time_ranges": [{"start": "09:00", "end": "17:00"}]
			}
		]
	}
}
```

- `Weekends only` : accessible only on Saturday and Sunday.

```json
{
	"domain": "streaming.example",
	"description": "Accessible only on weekends",
	"protected": false,
	"schedule": {
		"available_hours": [
			{
				"days": ["saturday", "sunday"],
				"time_ranges": [{"start": "00:00", "end": "23:59"}]
			}
		]
	}
}
```

- `Always blocked` : omit `schedule` or set it to `null`.

```json
{
	"domain": "always-blocked.example",
	"description": "Always blocked (no schedule)",
	"protected": false,
	"schedule": null
}
```

- `Protected always-block` : prevent CLI unblocking by setting `protected: true`.

```json
{
	"domain": "sensitive.example",
	"description": "Always blocked and protected",
	"protected": true,
	"schedule": null
}
```

Copy any snippet into your chosen example file (e.g. `minimal.json`) and edit `domain`, `days`, and `time_ranges` to match your needs.

