export interface AppConfig {
  pageTitle: string;
  pageDescription: string;
  companyName: string;

  supportsChatInput: boolean;
  supportsVideoInput: boolean;
  supportsScreenShare: boolean;
  isPreConnectBufferEnabled: boolean;

  logo: string;
  startButtonText: string;
  accent?: string;
  logoDark?: string;
  accentDark?: string;

  audioVisualizerType?: 'bar' | 'wave' | 'grid' | 'radial' | 'aura';
  audioVisualizerColor?: `#${string}`;
  audioVisualizerColorDark?: `#${string}`;
  audioVisualizerColorShift?: number;
  audioVisualizerBarCount?: number;
  audioVisualizerGridRowCount?: number;
  audioVisualizerGridColumnCount?: number;
  audioVisualizerRadialBarCount?: number;
  audioVisualizerRadialRadius?: number;
  audioVisualizerWaveLineWidth?: number;

  // agent dispatch configuration
  agentName?: string;

  // LiveKit Cloud Sandbox configuration
  sandboxId?: string;
}

export const APP_CONFIG_DEFAULTS: AppConfig = {
  companyName: 'Aarogya Mitra',
  pageTitle: 'Aarogya Mitra — Voice Health Access Assistant',
  pageDescription:
    'Your AI-powered voice health assistant. Navigate healthcare services, understand public health schemes, and prepare for doctor visits. Powered by Murf Falcon TTS.',

  supportsChatInput: true,
  supportsVideoInput: false,
  supportsScreenShare: false,
  isPreConnectBufferEnabled: true,

  logo: '/murf-logo.svg',
  accent: '#0d9488',
  logoDark: '/murf-logo-dark.svg',
  accentDark: '#2dd4bf',
  startButtonText: 'Talk to Aarogya Mitra',

  // Aura visualizer — a pulsing health-themed glow
  audioVisualizerType: 'aura',
  audioVisualizerColor: '#0d9488',
  audioVisualizerColorDark: '#2dd4bf',
  audioVisualizerColorShift: 0.25,

  // agent dispatch configuration
  agentName: process.env.AGENT_NAME ?? undefined,

  // LiveKit Cloud Sandbox configuration
  sandboxId: undefined,
};
