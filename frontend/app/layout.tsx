import { Public_Sans } from 'next/font/google';
import localFont from 'next/font/local';
import { headers } from 'next/headers';
import { ThemeProvider } from '@/components/app/theme-provider';
import { ThemeToggle } from '@/components/app/theme-toggle';
import { cn } from '@/lib/shadcn/utils';
import { getAppConfig, getStyles } from '@/lib/utils';
import '@/styles/globals.css';

const publicSans = Public_Sans({
  variable: '--font-public-sans',
  subsets: ['latin'],
});

const commitMono = localFont({
  display: 'swap',
  variable: '--font-commit-mono',
  src: [
    {
      path: '../fonts/CommitMono-400-Regular.otf',
      weight: '400',
      style: 'normal',
    },
    {
      path: '../fonts/CommitMono-700-Regular.otf',
      weight: '700',
      style: 'normal',
    },
    {
      path: '../fonts/CommitMono-400-Italic.otf',
      weight: '400',
      style: 'italic',
    },
    {
      path: '../fonts/CommitMono-700-Italic.otf',
      weight: '700',
      style: 'italic',
    },
  ],
});

interface RootLayoutProps {
  children: React.ReactNode;
}

export default async function RootLayout({ children }: RootLayoutProps) {
  const hdrs = await headers();
  const appConfig = await getAppConfig(hdrs);
  const styles = getStyles(appConfig);
  const { pageTitle, pageDescription } = appConfig;

  return (
    <html
      lang="en"
      suppressHydrationWarning
      className={cn(
        publicSans.variable,
        commitMono.variable,
        'scroll-smooth font-sans antialiased'
      )}
    >
      <head>
        {styles && <style>{styles}</style>}
        <title>{pageTitle}</title>
        <meta name="description" content={pageDescription} />
        {/* Noto Sans Devanagari for Hindi text rendering */}
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link
          href="https://fonts.googleapis.com/css2?family=Noto+Sans+Devanagari:wght@400;500;600;700&display=swap"
          rel="stylesheet"
        />
      </head>
      <body className="overflow-x-hidden">
        <ThemeProvider
          attribute="class"
          defaultTheme="system"
          enableSystem
          disableTransitionOnChange
        >
          <header className="fixed top-0 left-0 z-50 flex w-full flex-row items-center justify-between p-4 md:p-6">
            {/* Aarogya Mitra Logo & Brand */}
            <div className="flex items-center gap-2.5">
              {/* Health cross icon */}
              <div className="bg-primary/10 flex size-8 items-center justify-center rounded-lg">
                <svg
                  width="18"
                  height="18"
                  viewBox="0 0 24 24"
                  fill="none"
                  xmlns="http://www.w3.org/2000/svg"
                  className="text-primary"
                >
                  <path
                    d="M8 2v4H4a2 2 0 0 0-2 2v4a2 2 0 0 0 2 2h4v4a2 2 0 0 0 2 2h4a2 2 0 0 0 2-2v-4h4a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-4V2a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2z"
                    fill="currentColor"
                    fillOpacity="0.9"
                  />
                </svg>
              </div>
              <span className="text-foreground text-sm font-semibold tracking-tight">
                Aarogya Mitra
              </span>
            </div>

            {/* Powered by badge */}
            <span className="text-muted-foreground hidden font-mono text-[10px] font-bold tracking-wider uppercase md:block">
              Powered by{' '}
              <a
                target="_blank"
                rel="noopener noreferrer"
                href="https://murf.ai/api/docs/text-to-speech/streaming"
                className="text-primary/80 hover:text-primary underline underline-offset-4 transition-colors"
              >
                Murf Falcon
              </a>
            </span>
          </header>

          {children}
          <div className="group fixed bottom-0 left-1/2 z-50 mb-2 -translate-x-1/2">
            <ThemeToggle className="translate-y-20 transition-transform delay-150 duration-300 group-hover:translate-y-0" />
          </div>
        </ThemeProvider>
      </body>
    </html>
  );
}
