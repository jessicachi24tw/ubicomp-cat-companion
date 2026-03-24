"use client";

import { useEffect, useMemo, useState, useRef } from "react";

const max_heart = 10;

type QuestType = "hydration" | "stretch" | "plants" | "tidy";
type ReminderMode = "exact" | "timeframe";
type Timeframe = "morning" | "afternoon" | "evening";
const duration_options = [5, 10, 15, 20, 30];
const quest_options: { value: QuestType; label: string }[] = [
  { value: "hydration", label: "Drink water" },
  { value: "stretch", label: "Stretch" },
  { value: "plants", label: "Water plants" },
  { value: "tidy", label: "Tidy up" },
];

type Quest = {
  id: number;
  title: string;
  quest_type: QuestType;
  reminder_mode?: ReminderMode;
  reminder_time?: string;
  reminder_timeframe?: Timeframe;
  duration_minutes?: number;
  status: "pending" | "completed" | "skipped";
};

type InteractionLog = {
  id: number;
  message: string;
  timestamp: string;
};

type DashboardData = {
  heart_meter: number;
  quests: Quest[];
  interaction_logs: InteractionLog[];
};

function questLabelFromType(questType: QuestType) {
  return quest_options.find((q) => q.value === questType)?.label ?? questType;
}

export default function HomePage() {
  const [dashboard, setDashboard] = useState<DashboardData>({
    heart_meter: 0,
    quests: [],
    interaction_logs: [],
  });
  
  // play audio (chill lo-fi music) when the page loads 
  const audioRef = useRef<HTMLAudioElement | null>(null);
  useEffect(() => {
    const audio = audioRef.current;
    if (!audio) return;
    audio.volume = 0.35;
    const tryPlay = async () => {
      try {
        await audio.play();
      } catch {
        console.log("Autoplay was blocked by the browser.");
      }
    };
    tryPlay();
  }, []);

  const [questType, setQuestType] = useState<QuestType>("hydration");
  const [reminderMode, setReminderMode] = useState<ReminderMode>("exact");
  const [reminderTime, setReminderTime] = useState<string>("09:00");
  const [timeframe, setTimeframe] = useState<Timeframe>("morning");
  const [durationMinutes, setDurationMinutes] = useState<number>(10);

  // data fetching and processing 
  async function fetchDashboard() {
    try {
      const response = await fetch("http://localhost:8000/dashboard");
      if (!response.ok) {
        console.error("Failed to fetch dashboard:", response.status);
        return;
      }
      const data = await response.json();
      setDashboard({
        heart_meter: data.bond_level,
        quests: data.quests,
        interaction_logs: data.interaction_logs,
      });
    } catch (error) {
      console.error("Dashboard fetch error:", error);
    }
  }

  useEffect(() => {
    fetchDashboard();

    const interval = setInterval(() => {
      fetchDashboard();
    }, 3000);

    return () => clearInterval(interval);
  }, []);

  async function handleAddQuest(e: React.FormEvent) {
  e.preventDefault();
  
  // send newly added quest data to backend, then refresh the dashboard data to show the new quest
  const payload =
    reminderMode === "exact"
      ? {
          quest_type: questType,
          time_mode: "exact",
          exact_time: reminderTime,
          duration_minutes: durationMinutes,
        }
      : {
          quest_type: questType,
          time_mode: "timeframe",
          timeframe,
          duration_minutes: durationMinutes,
        };
  

  await fetch("http://localhost:8000/quests", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  })
  await fetchDashboard();
  }
  
  // delete a quest by id, then refreshing the dashboard data to reflect the change
  async function handleDeleteQuest(questId: number) {
  await fetch(`http://localhost:8000/quests/${questId}`, {
    method: "DELETE",
  });
  await fetchDashboard();
}
  // calculate heart meter percentage for display
  const currentHeart = Math.max(0, Math.min(dashboard.heart_meter, max_heart));
  console.log(dashboard.heart_meter)
  const heartPercent = useMemo(
    () => (currentHeart / max_heart) * 100,
    [currentHeart]
  );

  // main interface 
  return (
    <main className="page">
      <audio ref={audioRef} loop>
        <source src="/background.mp3" type="audio/mpeg" />
      </audio>
      <h1 className="title">Cat Companion Dashboard ₊˚⊹♡ ᓚ₍ ^. .^₎</h1>
      <p className="subtitle">
        On this dashboard, you can create daily quests which the cat will remind you to complete. 
        The more you interact with your cat and complete quests, the higher your heart meter goes. Have fun!
      </p>
      <div className="grid">
        <section className="card">
          <h2>Add a Daily Quest</h2>
          <form onSubmit={handleAddQuest}>
            <div className="form-row">
              <label>Quest</label>
              <select
                value={questType}
                onChange={(e) => setQuestType(e.target.value as QuestType)}
              >
                {quest_options.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </div>
            <div className="form-row">
              <label>Reminder type</label>
              <select
                value={reminderMode}
                onChange={(e) => setReminderMode(e.target.value as ReminderMode)}
              >
                <option value="exact">Specific time</option>
                <option value="timeframe">Broader timeframe</option>
              </select>
            </div>
            {reminderMode === "exact" ? (
              <div className="form-row">
                <label>Reminder time</label>
                <input
                  type="time"
                  value={reminderTime}
                  onChange={(e) => setReminderTime(e.target.value)}
                />
              </div>
            ) : (
              <div className="form-row">
                <label>Timeframe</label>
                <select
                  value={timeframe}
                  onChange={(e) => setTimeframe(e.target.value as Timeframe)}
                >
                  <option value="morning">Morning</option>
                  <option value="afternoon">Afternoon</option>
                  <option value="evening">Evening</option>
                </select>
              </div>
            )}
            <div className="form-row">
              <label>Quest duration (minutes)</label>
              <select
                value={durationMinutes}
                onChange={(e) => setDurationMinutes(Number(e.target.value))}
              >
                {duration_options.map((mins) => (
                  <option key={mins} value={mins}>
                    {mins} minutes
                  </option>
                ))}
              </select>
            </div>
            <button className="primary" type="submit">
              Add quest
            </button>
          </form>
        </section>
        <section className="card">
          <h2>Heart Meter</h2>
          <div className="meter-header">
            <span className="small">Level</span>
          </div>
          <div className="meter-outer" aria-label="heart meter">
            <div
              className="meter-inner"
              style={{ width: `${heartPercent}%` }}
            />
          </div>
          <p className="small">
            Your cat's bond level for today (maximum 10). 
            Each completed quest increases the level by 2, while each skipped 
            quest decreases it by 0.5. Petting your cat also increases the level by 1!
          </p>
        </section>
        <section className="card">
          <h2>Today's Quests</h2>
          {dashboard.quests.length === 0 ? (
            <p>No quests yet.</p>
          ) : (
            dashboard.quests.map((quest) => (
              <div className="quest-item" key={quest.id}>
                <strong>{quest.title || questLabelFromType(quest.quest_type)}</strong>
                <p>
                  Duration: {quest.duration_minutes ?? "—"} min
                  <br />
                  Reminder:{" "}
                  {quest.time_mode === "timeframe"
                    ? `${quest.timeframe ?? "—"} (${quest.scheduled_time ?? "—"})`
                    : quest.scheduled_time ?? quest.exact_time ?? "—"}
                </p>
                <div className="status-action">
                    <span className="status">{quest.status}</span>
                    <button className="primary" onClick={() => handleDeleteQuest(quest.id)}>
                      Remove
                    </button>
                </div>
              </div>
            ))
          )}
        </section>
        <section className="card">
          <h2>Interaction Logs</h2>
          {dashboard.interaction_logs.length === 0 ? (
            <p>No interactions yet.</p>
          ) : (
            dashboard.interaction_logs
              .slice()
              .reverse()
              .map((log) => (
                <div className="log-item" key={log.id}>
                  <div className="log-title-row">
                    <span>{log.message}</span>
                    <span
                      className={`heart-change ${
                        log.bond_change > 0 ? "heart-positive" : "heart-negative"
                      }`}
                    >
                      ({log.bond_change > 0 ? "+" : ""}
                      {log.bond_change})
                    </span>
                  </div>
                  <div className="small log-time">
                    {new Date(log.timestamp).toLocaleTimeString([], {
                      hour: "numeric",
                      minute: "2-digit",
                    })}
                  </div>
                </div>
              ))
          )}
        </section>
      </div>
    </main>
  );
}