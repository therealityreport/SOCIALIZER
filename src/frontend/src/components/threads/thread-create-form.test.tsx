import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { vi } from 'vitest';

import { ThreadCreateForm } from './thread-create-form';

const mutateMock = vi.fn();

vi.mock('../../hooks/useThreads', () => ({
  useCreateThread: () => ({
    mutate: mutateMock,
    isPending: false
  })
}));

describe('ThreadCreateForm', () => {
  beforeEach(() => {
    mutateMock.mockReset();
  });

  it('submits a new thread payload and surfaces success feedback', async () => {
    mutateMock.mockImplementation((_payload, options) => {
      options?.onSuccess?.({ id: 99 } as any);
    });

    render(<ThreadCreateForm />);
    const user = userEvent.setup();

    await user.type(
      screen.getByLabelText(/Thread URL/i),
      'https://www.reddit.com/r/bravo/comments/abc123/sample_thread'
    );
    await user.type(screen.getByLabelText(/Episode title/i), 'Bravo Premiere Night');
    await user.type(screen.getByLabelText(/Air time/i), '2024-01-01T20:00');
    await user.type(screen.getByLabelText(/Synopsis/i), 'Producers watchlist.');

    await user.click(screen.getByRole('button', { name: /Submit thread/i }));

    await waitFor(() => expect(mutateMock).toHaveBeenCalled());

    const payload = mutateMock.mock.calls[0][0];
    expect(payload).toMatchObject({
      reddit_id: 'abc123',
      subreddit: 'bravo',
      title: 'Bravo Premiere Night',
      url: 'https://www.reddit.com/r/bravo/comments/abc123/sample_thread',
      status: 'scheduled',
      synopsis: 'Producers watchlist.'
    });
    expect(payload.created_utc).toEqual(expect.any(String));

    expect(await screen.findByText(/Thread submitted! Aggregation will begin shortly./i)).toBeInTheDocument();
  });
});
