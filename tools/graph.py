import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import io


async def create_graph(data):
    dates, users = zip(*data)
    fig, ax = plt.subplots(figsize=(15, 8))

    ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
    plt.xticks(rotation=90)

    ax.grid(True)

    plt.plot(dates, users, marker='o', color='b', linestyle='-', linewidth=2, markersize=5)
    plt.xlabel('Дата регистрации')
    plt.ylabel('Количество новых пользователей')
    plt.title('Активность регистрации пользователей')

    # Добавление аннотаций
    for date, user_count in zip(dates, users):
        ax.annotate(f'{user_count}', xy=(date, user_count), xytext=(5, 5), textcoords='offset points')

    # Сохранение изображения в память
    img_data = io.BytesIO()
    plt.savefig(img_data, format='png')
    img_data.seek(0)

    return img_data
