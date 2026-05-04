# Reminder Workflow

Use local system time and timezone. Do not guess dates from model memory.

When the user gives natural language time, store both:

- original user text
- resolved schedule with timezone

Example:

```text
User schedule text: 每天晚上 9 点
Resolved schedule: daily 21:00 Asia/Shanghai
```

## Daily Reminder

The reminder must include learning content and require minimal input.

```text
【<Plan Name>｜Day X/N】
今天把 <topic> 接上。
最低完成：<minimum completion>

回 1：今天会学，我稍后提醒你收口
回 0：今天跳过，明天接上
回 低配：给我一个 10/20/30 分钟保底任务
```

## No Response

If no response after 60 minutes, send one light follow-up:

```text
刚才的学习提醒还没收到反馈。今天不用硬撑，回一个数字就行：

1 = 今天会学
0 = 今天跳过
低配 = 给我保底任务
```

After that, do not follow up again that day unless the user responds.

## Reply `1`

Meaning:

```text
1 = 今天会学，先记为学习中
```

Actions:

1. Mark today's state as studying.
2. Record response time.
3. Set expected close-out time to 2 hours later.
4. Send no extra question.

Close-out reminder:

```text
今天这节差不多该收口了。学完就回“下课”，我用 5 分钟帮你记录和验证。
```

Do not follow up again if the user does not respond to the close-out reminder.

## Reply `0`

Mark today as skipped. Do not shame the user.

Next reminder should reconnect from the same learning item unless the user asks to change plans.

## Low-Power Mode

Offer 10 / 20 / 30 minute choices:

```text
10 分钟：打开原材料，找到今天主题所在位置。
20 分钟：重看/重读核心部分，写一句话理解。
30 分钟：一句话理解 + 1 个验证问题。
```

Low-power mode preserves continuity. It does not automatically advance plan progress unless review shows mastery >= 3/5.

## Reply `下课`

Start close-out review:

1. Ask for one-sentence understanding.
2. Ask 1-3 small verification questions.
3. Score mastery.
4. Update dashboard and log.

Keep this within 5 minutes. If the user says they are tired, use a one-minute version.

## Missed Close-Out

If yesterday was studying but no close-out was recorded, the next daily reminder should first ask for a one-minute catch-up:

```text
昨天你已经把这个计划接上了，但没有下课记录。先补一句，避免内容散掉：
昨天主要学了什么？
```

Multiple missed close-outs are handled in weekly review, not daily reminders.
