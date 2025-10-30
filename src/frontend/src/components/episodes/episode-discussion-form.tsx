/**
 * Episode Discussion Form Component
 *
 * Form for creating new episode discussions with transcript upload
 */
import { FormEvent, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { CalendarDays, Upload, Users, Link as LinkIcon, Save, Play } from 'lucide-react';
import { Alert } from '../ui/alert';
import { Button } from '../ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../ui/card';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../ui/select';
import { Textarea } from '../ui/textarea';
import { Spinner } from '../ui/spinner';

type FormState = {
  show: string;
  season: string;
  episode: string;
  date: string;
  platform: string;
  links: string;
  transcriptText: string;
  window: string;
  castIds: string;
};

const initialForm: FormState = {
  show: '',
  season: '',
  episode: '',
  date: '',
  platform: 'reddit',
  links: '',
  transcriptText: '',
  window: 'DAY_OF',
  castIds: '',
};

export function EpisodeDiscussionForm() {
  const [form, setForm] = useState<FormState>(initialForm);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [statusMessage, setStatusMessage] = useState<{ type: 'success' | 'error'; message: string } | null>(null);
  const navigate = useNavigate();

  const handleChange = (
    event: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>
  ) => {
    const { name, value } = event.target;
    setForm((current) => ({ ...current, [name]: value }));
  };

  const handlePlatformChange = (value: string) => {
    setForm((current) => ({ ...current, platform: value }));
  };

  const handleWindowChange = (value: string) => {
    setForm((current) => ({ ...current, window: value }));
  };

  const validateForm = (): string | null => {
    if (!form.show.trim()) return 'Show name is required';
    if (!form.season || parseInt(form.season) < 1) return 'Valid season number is required';
    if (!form.episode || parseInt(form.episode) < 1) return 'Valid episode number is required';
    if (!form.date) return 'Episode date is required';
    if (!form.transcriptText.trim()) return 'Transcript text is required';
    return null;
  };

  const handleSubmit = async (event: FormEvent, saveAndAnalyze: boolean = false) => {
    event.preventDefault();
    setStatusMessage(null);

    const validationError = validateForm();
    if (validationError) {
      setStatusMessage({ type: 'error', message: validationError });
      return;
    }

    setIsSubmitting(true);

    try {
      // Parse links (comma or newline separated)
      const linksArray = form.links
        .split(/[,\n]/)
        .map((link) => link.trim())
        .filter((link) => link.length > 0);

      // Parse cast IDs (comma separated slugs)
      const castIdsArray = form.castIds
        .split(',')
        .map((id) => id.trim())
        .filter((id) => id.length > 0);

      const payload = {
        show: form.show.trim(),
        season: parseInt(form.season),
        episode: parseInt(form.episode),
        date_utc: new Date(form.date).toISOString(),
        platform: form.platform,
        links: linksArray,
        transcript_ref: `uploads/${form.show}_S${form.season}E${form.episode}.txt`, // Placeholder
        transcript_text: form.transcriptText,
        window: form.window,
        cast_ids: castIdsArray,
      };

      // Create episode discussion
      const response = await fetch('/api/episode-discussions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to create episode discussion');
      }

      const discussion = await response.json();

      // If "Save & Analyze" was clicked, trigger analysis
      if (saveAndAnalyze) {
        const analyzeResponse = await fetch(`/api/episode-discussions/${discussion.id}/analyze`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ force: false }),
        });

        if (!analyzeResponse.ok) {
          setStatusMessage({
            type: 'error',
            message: 'Discussion created but analysis failed to start. You can trigger it manually.',
          });
          return;
        }
      }

      setStatusMessage({
        type: 'success',
        message: saveAndAnalyze
          ? 'Episode discussion created and analysis started!'
          : 'Episode discussion saved as draft!',
      });

      // Reset form and navigate after success
      setTimeout(() => {
        setForm(initialForm);
        navigate(`/episode-discussions/${discussion.id}`);
      }, 1500);
    } catch (error) {
      setStatusMessage({
        type: 'error',
        message: error instanceof Error ? error.message : 'An error occurred',
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-xl">
          <Upload className="h-5 w-5 text-primary" />
          Add New Episode Discussion
        </CardTitle>
        <CardDescription>
          Upload an episode transcript and social media links for LLM-powered sentiment analysis.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form className="space-y-6">
          {statusMessage && (
            <Alert variant={statusMessage.type === 'success' ? 'default' : 'destructive'}>
              {statusMessage.message}
            </Alert>
          )}

          {/* Episode Metadata */}
          <div className="space-y-4">
            <h3 className="text-sm font-semibold">Episode Metadata</h3>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="space-y-2">
                <Label htmlFor="show">Show *</Label>
                <Input
                  id="show"
                  name="show"
                  value={form.show}
                  onChange={handleChange}
                  placeholder="The Real Housewives of..."
                  required
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="season">Season *</Label>
                <Input
                  id="season"
                  name="season"
                  type="number"
                  min="1"
                  value={form.season}
                  onChange={handleChange}
                  placeholder="6"
                  required
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="episode">Episode *</Label>
                <Input
                  id="episode"
                  name="episode"
                  type="number"
                  min="1"
                  value={form.episode}
                  onChange={handleChange}
                  placeholder="12"
                  required
                />
              </div>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="date" className="flex items-center gap-2">
                  <CalendarDays className="h-4 w-4" />
                  Air Date *
                </Label>
                <Input
                  id="date"
                  name="date"
                  type="date"
                  value={form.date}
                  onChange={handleChange}
                  required
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="platform">Platform *</Label>
                <Select value={form.platform} onValueChange={handlePlatformChange}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="reddit">Reddit</SelectItem>
                    <SelectItem value="instagram">Instagram</SelectItem>
                    <SelectItem value="tiktok">TikTok</SelectItem>
                    <SelectItem value="x">X (Twitter)</SelectItem>
                    <SelectItem value="youtube">YouTube</SelectItem>
                    <SelectItem value="other">Other</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
          </div>

          {/* Discussion Links */}
          <div className="space-y-2">
            <Label htmlFor="links" className="flex items-center gap-2">
              <LinkIcon className="h-4 w-4" />
              Discussion Links
            </Label>
            <Textarea
              id="links"
              name="links"
              value={form.links}
              onChange={handleChange}
              placeholder="https://reddit.com/r/BravoRealHousewives/...&#10;https://reddit.com/r/RHOSLC/..."
              rows={3}
            />
            <p className="text-xs text-muted-foreground">Enter multiple URLs separated by commas or newlines</p>
          </div>

          {/* Transcript */}
          <div className="space-y-2">
            <Label htmlFor="transcriptText" className="flex items-center gap-2">
              <Upload className="h-4 w-4" />
              Episode Transcript *
            </Label>
            <Textarea
              id="transcriptText"
              name="transcriptText"
              value={form.transcriptText}
              onChange={handleChange}
              placeholder="Paste the full episode transcript here..."
              rows={10}
              required
            />
            <p className="text-xs text-muted-foreground">
              Supports plain text, VTT, SRT, or JSON formats
            </p>
          </div>

          {/* Additional Options */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="window">Discussion Window</Label>
              <Select value={form.window} onValueChange={handleWindowChange}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="LIVE">Live (during airing)</SelectItem>
                  <SelectItem value="DAY_OF">Day Of (default)</SelectItem>
                  <SelectItem value="AFTER">After (post-airing)</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="castIds" className="flex items-center gap-2">
                <Users className="h-4 w-4" />
                Cast Member IDs
              </Label>
              <Input
                id="castIds"
                name="castIds"
                value={form.castIds}
                onChange={handleChange}
                placeholder="lisa_barlow,heather_gay,meredith_marks"
              />
              <p className="text-xs text-muted-foreground">Comma-separated cast member slugs</p>
            </div>
          </div>

          {/* Submit Buttons */}
          <div className="flex gap-3 pt-4">
            <Button
              type="button"
              variant="outline"
              onClick={(e) => handleSubmit(e, false)}
              disabled={isSubmitting}
              className="flex-1"
            >
              {isSubmitting ? (
                <>
                  <Spinner className="mr-2 h-4 w-4" />
                  Saving...
                </>
              ) : (
                <>
                  <Save className="mr-2 h-4 w-4" />
                  Save Draft
                </>
              )}
            </Button>
            <Button
              type="button"
              onClick={(e) => handleSubmit(e, true)}
              disabled={isSubmitting}
              className="flex-1"
            >
              {isSubmitting ? (
                <>
                  <Spinner className="mr-2 h-4 w-4" />
                  Processing...
                </>
              ) : (
                <>
                  <Play className="mr-2 h-4 w-4" />
                  Save & Analyze
                </>
              )}
            </Button>
          </div>
        </form>
      </CardContent>
    </Card>
  );
}
