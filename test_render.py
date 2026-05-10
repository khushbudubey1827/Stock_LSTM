from app import app
from flask import render_template

with app.test_request_context('/'):
    print('LIVE PRICE RENDER:')
    live_data = {
        'ticker': 'AAPL',
        'price': 150.0,
        'prev_close': 145.0,
        'change': 5.0,
        'change_pct': 3.4,
        'direction': 'up',
        'open': 146.0,
        'high': 152.0,
        'low': 145.5,
        'high_52w': 180.0,
        'low_52w': 120.0,
        'chart_prices': [145, 146, 148, 150],
    }
    try:
        html = render_template('live_price.html', stock='AAPL', live_data=live_data, user_name='Test')
        print('Live Price Rendered Successfully. Length:', len(html))
        if 'id="priceChart"' not in html:
            print('Chart is missing from output!')
    except Exception as e:
        print('Error rendering live_price:', str(e))

    print('\nNEXT DAY RENDER:')
    prediction = {
        'price': 155.0,
        'last_price': 150.0,
        'change': 5.0,
        'change_pct': 3.3,
        'direction': 'UP',
        'signal': 'BUY',
    }
    try:
        html = render_template(
            'next_day_prediction.html',
            stock='AAPL',
            prediction=prediction,
            user_name='Test',
            history_prices=[{'day': 'Mon', 'price': 140}],
        )
        print('Next Day Rendered Successfully. Length:', len(html))
    except Exception as e:
        print('Error rendering next_day:', str(e))

    print('\nSENTIMENT RENDER:')
    sentiment = {
        'articles': [
            {
                'title': 'Test',
                'url': '#',
                'source': 'News',
                'time': '2026-01-01',
                'label': 'Positive',
                'color': 'green',
                'score': 0.8,
            }
        ],
        'overall': 'Bullish',
        'overall_color': 'green',
        'avg_score': 0.5,
        'positive': 1,
        'negative': 0,
        'neutral': 0,
        'total': 1,
    }
    try:
        html = render_template('sentiment_analysis.html', stock='AAPL', sentiment=sentiment, user_name='Test')
        print('Sentiment Rendered Successfully. Length:', len(html))
    except Exception as e:
        print('Error rendering sentiment:', str(e))
