# NakshatraAI Web UI

Beautiful, modern web interface for the NakshatraAI astrology chatbot.

## Features

✨ **Modern Design**
- Glassmorphism UI with blur effects
- Smooth animations and transitions
- Dark/Light mode toggle
- Fully responsive (mobile + desktop)

💬 **Chat Interface**
- Real-time conversations
- Typing indicators
- Message history
- Quick suggestion chips

👤 **Profile Management**
- Birth data input
- Profile saving/editing
- Birth chart calculation
- Chart visualization

## Quick Start

### 1. Start the API Server

```bash
uvicorn src.api.main:app --reload
```

### 2. Open in Browser

```
http://localhost:8000
```

The root URL now automatically serves the Web UI!

## First-Time Setup

1. **Enter API Key**
   - When you first open the app, you'll be prompted for an API key
   - Use the same key from your `.env` file (`VALID_API_KEYS`)
   - Example: `my-dev-key-123`

2. **Create Profile** (Optional)
   - Click the profile button (👤) in the header
   - Enter your birth information
   - Save to enable personalized responses

3. **Start Chatting!**
   - Ask astrology questions
   - Request birth chart calculations
   - Get personalized insights

## File Structure

```
static/
├── index.html              # Main page
├── css/
│   └── styles.css         # Glassmorphism design
└── js/
    ├── api.js             # API client
    ├── chat.js            # Chat logic
    ├── profile.js         # Profile management
    └── app.js             # Main app controller
```

## Features in Detail

### Chat Interface

- **Suggestion Chips**: Quick-start questions
- **Typing Indicators**: Shows when bot is thinking
- **Message History**: Conversation context maintained
- **Error Handling**: Clear error messages

### Profile Management

- **Birth Data**: Date, time, location
- **Coordinates**: Latitude/longitude for calculations
- **Timezone**: Accurate time conversions
- **Chart Viewing**: Instant birth chart display

### Theme Toggle

- **Light Mode**: Clean, bright interface
- **Dark Mode**: Eye-friendly dark theme
- **Auto-saved**: Preference stored in browser

## API Integration

The UI connects to these FastAPI endpoints:

- `POST /api/v1/chat` - Send messages
- `GET /api/v1/user/{id}` - Get profile
- `POST /api/v1/user` - Create profile
- `PUT /api/v1/user/{id}` - Update profile
- `POST /api/v1/calculate/chart` - Birth chart

## Browser Support

- Chrome/Edge (latest)
- Firefox (latest)
- Safari (latest)
- Mobile browsers

## Development

### Adding Features

1. **New API Endpoints**: Update `js/api.js`
2. **UI Components**: Add to `index.html`
3. **Styling**: Modify `css/styles.css`
4. **Logic**: Update relevant JS file

### Local Storage

The app stores:
- `nakshatra_api_key` - API key
- `nakshatra_user_id` - User ID
- `nakshatra_theme` - Theme preference

## Tips

- **Mobile**: Fully responsive, works on all devices
- **Keyboard**: Press Enter to send messages
- **API Key**: Stored securely in browser only
- **Charts**: View directly in profile modal

## Screenshots

### Chat Interface
Beautiful glassmorphism design with gradient backgrounds and smooth animations.

### Profile Management
Easy-to-use form for birth data with instant chart calculation.

### Dark Mode
Eye-friendly dark theme with full feature parity.

## Troubleshooting

**"Cannot connect to API"**
- Make sure the FastAPI server is running
- Check it's on `http://localhost:8000`
- Verify CORS is enabled

**"Invalid API key"**
- Check your `.env` file for `VALID_API_KEYS`
- Re-enter the key in the browser prompt

**Charts not showing**
- Ensure all birth data fields are filled
- Check latitude/longitude are valid numbers
- Verify API server has access to calculation engine

## Next Steps

- Add more chart visualizations
- Implement conversation export
- Add voice input support
- Multi-language support

Enjoy exploring the stars! ✨🔮
