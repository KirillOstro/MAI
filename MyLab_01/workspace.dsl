workspace {
    name "BlaBlaCar"
    description "Сервис поиска попутчиков"

    # включаем режим с иерархической системой идентификаторов
    !identifiers hierarchical

    model {
        my_user = person "Пользователь сервиса"

        my_system = softwareSystem "BlaBlaCar.ru" {
            description "Сервис организации дешевых поездок"

            #Компоненты сервиса

            my_app = container "WebApp" {
                description "Сайт/приложение для доступа к сервису BlaBlaCar"
                technology "JS"
            }

            u_service = container "User Service"{
                description "Сервис по управлению данными пользователей"
                technology "JS"
            }

            r_service = container "Route Service" {
                description "Сервис по управлению данными маршрутов"
                technology "JS"
            }

            t_service = container "Trip Service" {
                description "Сервис по управлению данными поездок"
                technology "JS"
            }
            
            u_base = container "User Database" {
                description "База данных пользователей"
                technology "PostgreSQL"
            }

            r_base = container "Route Database" {
                description "База данных маршрутов"
                technology "PostgreSQL"
            }
            
            t_base = container "Trip Database" {
                description "База данных поездок"
                technology "PostgreSQL"
            }


            # Взаимодействия пользователя с сайтом
            my_user -> my_app "Регистрация" "HTTPS"

            my_user -> my_app "Поиск пользователя по логину" "HTTPS"

            my_user -> my_app "Поиск пользователя по маске имя и фамилии" "HTTPS"

            my_user -> my_app "Создание маршрута" "HTTPS"

            my_user -> my_app "Получение маршрута пользователя" "HTTPS"

            my_user -> my_app "Создание поездки" "HTTPS"

            my_user -> my_app "Подключение пользователей к поездке" "HTTPS"

            my_user -> my_app "Получение информации о поездке" "HTTPS"

            # Запросы сайта к сервисам

            my_app -> u_service "Запрос на создание нового пользователя" "JS"

            my_app -> u_service "Запрос на поиск пользователя" "JS"

            my_app -> r_service "Запрос на создание нового маршрута" "JS"

            my_app -> r_service "Запрос на получение маршрута пользователя" "JS"

            my_app -> t_service "Запрос на создание поездки" "JS"

            my_app -> t_service "Запрос на подключение пользователей к поездке" "JS"

            my_app -> t_service "Запрос на получение информации о поездке" "JS"

            # Запросы сервисов к базам данных

            u_service -> u_base "INSERT into users (name/mail/psw)" "PostgreSQL"

            u_service -> u_base "GET * from users WHERE login = {x}" "PostgreSQL"

            u_service -> u_base "GET * from users WHERE name = {x} AND surname = {y}" "PostgreSQL"

            r_service -> r_base "INSERT into routes (userid/points)" "PostgreSQL"

            r_service -> r_base "GET * from routes WHERE userid = {x}" "PostgreSQL"

            t_service -> t_base "INSERT into trips (userid/route)" "PostgreSQL"

            t_service -> u_service "Получение информации о пользователе для подключения к поездке" "JS"

            t_service -> t_base "INSERT into trips (companions)" "PostgreSQL"

            t_service -> t_base "GET * from trips WHERE tripid = {x}"

        }
    }

    views {
        # Задаем стили для отображения
        themes default

        # Диаграмма контекста
        systemContext my_system {
            include *
            autoLayout lr
        }

        container my_system {
            include *
            autoLayout lr
        }

        dynamic my_system "registry" "Регистрация пользователя" {
            autoLayout lr
            my_user -> my_system.my_app "Регистрация" "HTTPS"
            my_system.my_app -> my_system.u_service "Запрос на создание нового пользователя" "JS"
            my_system.u_service -> my_system.u_base "INSERT into users (name/mail/psw)" "PostgreSQL"
        }

        dynamic my_system "login_search" "Поиск пользователя по логину" {
            autoLayout lr
            my_user -> my_system.my_app "Поиск пользователя по логину" "HTTPS"
            my_system.my_app -> my_system.u_service "Запрос на поиск пользователя" "JS"
            my_system.u_service -> my_system.u_base "GET * from users WHERE login = {x}" "PostgreSQL"
        }

        dynamic my_system "name_search" "Поиск пользователя по маске имя и фамилии" {
            autoLayout lr
            my_user -> my_system.my_app "Поиск пользователя по маске имя и фамилии" "HTTPS"
            my_system.my_app -> my_system.u_service "Запрос на поиск пользователя" "JS"
            my_system.u_service -> my_system.u_base "GET * from users WHERE name = {x} AND surname = {y}" "PostgreSQL"
        }

        dynamic my_system "create_route" "Создание маршрута" {
            autoLayout lr
            my_user -> my_system.my_app "Создание маршрута" "HTTPS"
            my_system.my_app -> my_system.r_service "Запрос на создание нового маршрута" "JS"
            my_system.r_service -> my_system.r_base "INSERT into routes (userid/points)" "PostgreSQL"
        }

        dynamic my_system "route_name_search" "Получение маршрута пользователя" {
            autoLayout lr
            my_user -> my_system.my_app "Получение маршрута пользователя" "HTTPS"
            my_system.my_app -> my_system.r_service "Запрос на получение маршрута пользователя" "JS"
            my_system.r_service -> my_system.r_base "GET from routes WHERE userid = {x}" "PostgreSQL"
        }

        dynamic my_system "create_trip" "Создание поездки" {
            autoLayout lr
            my_user -> my_system.my_app "Создание поездки" "HTTPS"
            my_system.my_app -> my_system.t_service "Запрос на создание поездки" "JS"
            my_system.t_service -> my_system.t_base "INSERT into trips (userid/route)" "PostgreSQL"
        }

        dynamic my_system "add_companion" "Подключение пользователей к поездке" {
            autoLayout lr
            my_user -> my_system.my_app "Подключение пользователей к поездке" "HTTPS"
            my_system.my_app -> my_system.t_service "Запрос на подключение пользователей к поездке" "JS"
            my_system.t_service -> my_system.u_service "Получение информации о пользователе для подключения к поездке" "JS"
            my_system.t_service -> my_system.t_base "INSERT into trips (companions)" "PostgreSQL"
        }

        dynamic my_system "trip_search" "Получение информации о поездке" {
            autoLayout lr
            my_user -> my_system.my_app "Получение информации о поездке" "HTTPS"
            my_system.my_app -> my_system.t_service "Запрос на получение информации о поездке" "JS"
            my_system.t_service -> my_system.t_base "GET * from trips WHERE tripid = {x}" "PostgreSQL"
        }


    }
}