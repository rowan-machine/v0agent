# SignalFlow Mobile App

React Native mobile companion for SignalFlow - your AI-powered meeting intelligence and knowledge management system.

## Features

- 📱 **Offline-First**: Work without internet, sync when connected
- 🔄 **Real-Time Sync**: Instant updates via Supabase real-time subscriptions
- 🎯 **Sprint Dashboard**: Track tickets with drag-and-drop status updates
- 📊 **Meeting Signals**: View extracted decisions, actions, blockers, and risks
- 🧠 **DIKW Browser**: Browse your knowledge pyramid on the go
- 📝 **Quick Standup**: Submit daily standups from anywhere
- 🔔 **Push Notifications**: Get notified of important signals and blockers

## Tech Stack

- **Framework**: React Native with Expo SDK 50
- **Navigation**: React Navigation 6
- **State Management**: Zustand
- **Data Fetching**: TanStack React Query
- **Backend**: Supabase (PostgreSQL + Auth + Real-time)
- **Build**: EAS Build for APK/IPA generation

## Getting Started

### Prerequisites

- Node.js 18+
- npm or yarn
- Expo CLI (`npm install -g expo-cli`)
- EAS CLI (`npm install -g eas-cli`)
- Expo Go app on your device (for development)

### Installation

```bash
cd mobile
npm install
```

### Environment Setup

Create a `.env` file:

```env
EXPO_PUBLIC_SUPABASE_URL=https://your-project.supabase.co
EXPO_PUBLIC_SUPABASE_ANON_KEY=your-anon-key
```

### Running the App

```bash
# Start development server
npm start

# Run on Android
npm run android

# Run on iOS
npm run ios
```

### Building for Production

```bash
# Build Android APK
npm run build:android

# Build iOS (requires Apple Developer account)
npm run build:ios
```

## Project Structure

```
mobile/
├── src/
│   ├── App.tsx              # Main app entry with navigation
│   ├── screens/             # Screen components
│   │   ├── HomeScreen.tsx   # Dashboard with quick stats
│   │   ├── MeetingsScreen.tsx
│   │   ├── TicketsScreen.tsx
│   │   ├── KnowledgeScreen.tsx
│   │   └── SettingsScreen.tsx
│   ├── services/
│   │   ├── api.ts           # Supabase client & API helpers
│   │   └── sync.ts          # Offline-first sync service
│   ├── stores/
│   │   ├── authStore.ts     # Authentication state
│   │   └── syncStore.ts     # Sync status state
│   └── types/               # TypeScript definitions
├── assets/                  # Images, icons, splash screens
├── app.json                 # Expo configuration
├── eas.json                 # EAS Build configuration
└── package.json
```

## Sync Architecture

The app uses an offline-first architecture:

1. **Write Path**: All mutations go to local queue first
2. **Sync Queue**: Pending changes stored in SecureStore
3. **Background Sync**: Queue processed when online
4. **Real-Time**: Supabase subscriptions for instant updates
5. **Conflict Resolution**: Last-write-wins with timestamps

## Contributing

This is part of the SignalFlow project. See the main README for contribution guidelines.
