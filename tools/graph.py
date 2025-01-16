import io

import matplotlib.dates as mdates
import matplotlib.pyplot as plt


async def create_graph(data):
    months, user_counts = zip(*data)
    fig, ax = plt.subplots(figsize=(15, 8))

    ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
    plt.xticks(rotation=90)

    ax.grid(True)

    plt.bar(months, user_counts, color='b', width=20)
    plt.xlabel('Месяц регистрации')
    plt.ylabel('Количество новых пользователей')
    plt.title('Активность регистрации пользователей по месяцам')

    for month, user_count in zip(months, user_counts):
        ax.annotate(f'{user_count}', xy=(month, user_count), xytext=(5, user_count + 5), textcoords='offset points')

    img_data = io.BytesIO()
    plt.savefig(img_data, format='png')
    img_data.seek(0)

    return img_data
