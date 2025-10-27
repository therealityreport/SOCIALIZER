import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

import { CastGrid } from './cast-grid';

const baseMetrics = {
  net_sentiment: 0.2,
  ci_lower: 0.1,
  ci_upper: 0.3,
  positive_pct: 0.6,
  neutral_pct: 0.3,
  negative_pct: 0.1,
  agreement_score: 0.8,
  mention_count: 25
};

describe('CastGrid', () => {
  it('renders cast analytics cards with share of voice and sentiment data', () => {
    const cast = [
      {
        cast_id: 1,
        cast_slug: 'lisa-barlow',
        full_name: 'Lisa Barlow',
        show: 'RHOSLC',
        share_of_voice: 0.42,
        overall: baseMetrics,
        time_windows: {
          live: { ...baseMetrics, mention_count: 15 },
          day_of: { ...baseMetrics, net_sentiment: 0.1, mention_count: 10 }
        },
        sentiment_shifts: {
          day_of_vs_live: -0.1
        }
      }
    ];

    render(
      <MemoryRouter>
        <CastGrid threadId={123} cast={cast as any} />
      </MemoryRouter>
    );

    expect(screen.getByText('Lisa Barlow')).toBeInTheDocument();
    expect(screen.getByText('RHOSLC')).toBeInTheDocument();
    expect(screen.getByText('42.0%')).toBeInTheDocument();
    expect(screen.getByText('live')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /Dive deeper/i })).toHaveAttribute('href', '/threads/123/cast/lisa-barlow');
  });
});
