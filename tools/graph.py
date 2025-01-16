import matplotlib.pyplot as plt
import io


async def create_graph(data):
    dates, users = zip(*data)
    plt.plot(dates, users)
    plt.xlabel('Дата регистрации')
    plt.ylabel('Количество новых пользователей')
    plt.title('Активность регистрации пользователей')

    img_data = io.BytesIO()
    plt.savefig(img_data, format='png')
    img_data.seek(0)

    return img_data
