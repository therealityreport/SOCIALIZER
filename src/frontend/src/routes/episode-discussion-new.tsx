/**
 * New Episode Discussion Page
 *
 * Route: /episode-discussions/new
 */
import { EpisodeDiscussionForm } from '../components/episodes/episode-discussion-form';

export default function NewEpisodeDiscussionPage() {
  return (
    <div className="container mx-auto py-8 max-w-4xl">
      <EpisodeDiscussionForm />
    </div>
  );
}
