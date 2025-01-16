import io

import matplotlib.pyplot as plt
import matplotlib.dates as mdates


async def create_graph(data):
    dates, users = zip(*data)
    fig, ax = plt.subplots()

    # Поворот меток оси X
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
    plt.xticks(rotation=45)

    # Добавление сетки
    ax.grid(True)

    # Построение графика
    plt.plot(dates, users, marker='o', color='b')
    plt.xlabel('Дата регистрации')
    plt.ylabel('Количество новых пользователей')
    plt.title('Активность регистрации пользователей')

    # Сохранение изображения в память
    img_data = io.BytesIO()
    plt.savefig(img_data, format='png')
    img_data.seek(0)

    return img_data
