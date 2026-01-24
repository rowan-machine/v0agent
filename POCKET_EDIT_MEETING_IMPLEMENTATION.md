# Pocket Lookup Integration on Edit Meeting Page

## Overview
Added Pocket recording lookup functionality to the "Edit Meeting" page, allowing users to find recent Pocket recordings and select specific versions of AI-generated summaries and mind maps to load into their meeting.

## Changes Made

### 1. API Endpoints (main.py)

#### New Endpoint: `/api/integrations/pocket/fetch-versions`
- **Method**: POST
- **Purpose**: Fetch all available summary and mind map versions from a Pocket recording
- **Parameters**: `recording_id`
- **Returns**: 
  - `summary_versions`: List of available summary versions with labels
  - `mind_map_versions`: List of available mind map versions
  - `transcript_text`: Full transcript (if available)
  - `action_items`: Extracted action items (if available)

#### Updated Endpoint: `/api/integrations/pocket/fetch`
- **Enhancement**: Added support for version selection parameters
- **New Parameters**: 
  - `summary_key`: Specific summary version to fetch (e.g., 'v2_summary', 'v1_summary')
  - `mind_map_key`: Specific mind map version to fetch (e.g., 'v2_mind_map')
- **Behavior**: 
  - If no version key is specified, fetches the latest version (backward compatible)
  - If version key is specified, fetches that specific version

### 2. Database Schema Updates (db.py)

#### New Column: `pocket_mind_map`
- Added `pocket_mind_map TEXT` column to `meeting_summaries` table
- Includes migration to add column if it doesn't exist
- Stores the structured mind map from Pocket in a searchable format

### 3. Frontend Updates (edit_meeting.html)

#### New UI Section: "🔗 Pocket Recording Lookup"
- **Location**: Below "Pocket Transcript" section in the edit form
- **Features**:
  - Recording selector dropdown (auto-loaded with recent recordings)
  - Summary version selector (populated dynamically)
  - Mind map version selector (populated dynamically)
  - "Load Selected Versions" button
  - Status messages (loading, success, error)

#### JavaScript Functions:
- `loadPocketRecordings()`: Fetches and populates the recording dropdown
- `fetchVersionsOnChange()`: Triggered when recording is selected, shows version options
- `loadPocketVersions()`: Loads selected versions and auto-fills the form

#### Form Fields:
- Added hidden field `pocket_mind_map_field` to store the selected mind map
- Existing `pocket_ai_summary` field used for summary auto-fill

### 4. Backend Form Handler Updates (meetings.py)

#### Updated `update_meeting()` function:
- Added `pocket_mind_map` parameter
- Updated SQL UPDATE statement to save both `pocket_ai_summary` and `pocket_mind_map`
- Parameters: Both fields are optional (defaults to empty string if not provided)

## User Workflow

1. **Open Edit Meeting Page**: Click on a meeting to edit it
2. **Expand Pocket Lookup Section**: Click "Show/Hide" in the "🔗 Pocket Recording Lookup" section
3. **Select Recording**: Choose from recent Pocket recordings in the dropdown
4. **Review Available Versions**: Dropdown automatically populated with:
   - Available summary versions (v2, v1, etc.)
   - Available mind map versions
5. **Select Desired Versions**: Choose which version to use for each (optional)
6. **Load**: Click "Load Selected Versions" button
7. **Verify**: Summary and mind map auto-fill in their respective fields
8. **Save**: Click "Save Changes" to persist the updates

## Key Features

✅ **Version Selection**: Users can choose between multiple AI-generated versions
✅ **Auto-fill**: Selected content automatically populates form fields
✅ **Non-destructive**: Only updates fields user explicitly selects
✅ **Error Handling**: User-friendly error messages if Pocket API calls fail
✅ **Status Messages**: Clear feedback on what was loaded
✅ **Backward Compatible**: Existing code continues to work unchanged
✅ **Optional Fields**: Both Pocket summary and mind map are optional

## Technical Details

### API Response Format for fetch-versions:
```json
{
  "success": true,
  "recording_id": "rec_123",
  "summary_versions": [
    {
      "key": "v2_summary",
      "text": "...",
      "version": "2",
      "label": "V2 Summary (v2)"
    }
  ],
  "mind_map_versions": [
    {
      "key": "v2_mind_map",
      "text": "...",
      "type": "structured",
      "label": "V2 Mind Map"
    }
  ],
  "transcript_text": "...",
  "action_items": [...]
}
```

### API Response Format for fetch with version selection:
```json
{
  "success": true,
  "recording_id": "rec_123",
  "summary_text": "...",
  "mind_map_text": "...",
  "transcript_text": "...",
  "action_items": [...]
}
```

## Integration with Existing Features

- **Pocket Recording List**: Uses existing `/api/integrations/pocket/recordings` endpoint
- **Summary Extraction**: Reuses `get_all_summary_versions()` function from pocket.py
- **Mind Map Extraction**: Reuses `get_all_mind_map_versions()` function from pocket.py
- **Form Handling**: Integrates seamlessly with existing meeting edit form

## Testing Checklist

- [x] API endpoints return correct version lists
- [x] Version selection parameters work correctly
- [x] UI populates recording dropdown on page load
- [x] Version selectors populate when recording is selected
- [x] "Load Selected Versions" button fetches and populates form
- [x] Database schema migration creates pocket_mind_map column
- [x] Form saves pocket_mind_map correctly
- [x] Error handling works for API failures
- [x] Status messages display appropriately

## Files Modified

1. `/Users/rowan/v0agent/src/app/main.py` - Added new endpoints
2. `/Users/rowan/v0agent/src/app/meetings.py` - Updated form handler
3. `/Users/rowan/v0agent/src/app/db.py` - Added database column
4. `/Users/rowan/v0agent/src/app/templates/edit_meeting.html` - Added UI section and JavaScript

## Future Enhancements

- [ ] Add ability to preview version content before loading
- [ ] Show creation date/time for each version
- [ ] Add version comparison view
- [ ] Auto-select "best" version based on quality scores
- [ ] Store version metadata for auditing
