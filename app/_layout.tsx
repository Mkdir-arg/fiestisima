import { Stack } from 'expo-router';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ApiError } from '@/src/lib/api';
import { SessionProvider } from '@/src/features/auth/SessionProvider';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // A 4xx is not worth retrying (the request is wrong, not the network),
      // and react-query's default of 3 retries with backoff would otherwise
      // leave a screen showing its loading state for ~7s before a client
      // error like 403/404/422 ever reaches it. 5xx and network failures
      // still get a couple of retries.
      retry: (failureCount, error) =>
        !(error instanceof ApiError && error.status < 500) && failureCount < 2,
    },
  },
});

export default function RootLayout() {
  return (
    <QueryClientProvider client={queryClient}>
      <SessionProvider>
        <Stack screenOptions={{ headerShown: false }} />
      </SessionProvider>
    </QueryClientProvider>
  );
}
