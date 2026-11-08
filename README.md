# UltimaDesk

Rice Frutiger Aero para Arch Linux/EndeavourOS com Hyprland.

## Instalacao

Pode executar do Plasma ou de qualquer outra sessao; nao precisa abrir o Hyprland antes. Dentro desta pasta, rode:

```bash
./install.sh
```

O instalador unico instala as dependencias, ativa NetworkManager/Bluetooth/PipeWire, configura Waybar e notificacoes, gera um wallpaper, compila o globo quando os dados Natural Earth estao disponiveis e integra a inicializacao ao Hyprland. Se nao houver configuracao Hyprland, cria uma configuracao `.conf` minima com o rice e detecta o modo de monitor ativo pelo KScreen; ao executar pelo Plasma, tudo fica preparado para a proxima entrada no Hyprland. Os arquivos `install-waybar.sh`, `ultimadesk-setup/install.sh` e `waybar-aero/globo-layer/build.sh` agora encaminham para esse mesmo instalador.

As configuracoes existentes do Waybar sao copiadas para arquivos `.backup-*` quando diferem das padroes. Wallpapers ja existentes sao preservados. Um `ultimadesk.conf` ou `ultimadesk.lua` antigo e guardado como backup antes da migracao. O instalador encerra o globo Raylib e paineis antigos, instala o globo transparente em Wayland layer-shell e reinicia o rice se chamado dentro da sessao.

## Controles

Clique nas tres barras ou use `Super+I` para abrir o painel geral. Os indicadores de volume, Wi-Fi e Bluetooth abrem diretamente a secao correspondente; audio, microfone, redes e dispositivos ficam separados. A barra superior mostra hora, CPU e RAM junto dos indicadores, e o nome da rede Wi-Fi substitui a porcentagem de sinal.

O launcher proprio do rice abre por `Super+D` ou pelo icone de aplicativos. Digite para filtrar, use setas/Enter para navegar e `Esc` para fechar; escolher um app fecha o launcher automaticamente. As barras laterais e superior se encontram sem a antiga lacuna. O globo pausa somente enquanto o workspace ativo tiver janelas; ao mudar para um workspace vazio, ele volta a girar.

Atalhos adicionados:

- `Super+Enter`: terminal
- `Super+E`: arquivos
- `Super+D`: aplicativos
- `Super+W`: visão de todos os workspaces e janelas abertas; clique numa janela para focá-la
- `Super+Alt`: alternar tela cheia da janela focada
- `Super+B`: navegador
- `Super+V`: historico do clipboard
- `Super+L`: bloquear
- `Super+M`: menu de energia
- `Super+Shift+Q`: sair do Hyprland e voltar ao gerenciador de login
- `Super+Shift+S` ou `Print`: menu de capturas, com area/tela para clipboard ou arquivo
- `Super+Q`: fechar janela; `Super+F`: tela cheia; `Super+Space`: flutuar janela
- `Super+P`: pseudo-tile; `Super+O`: alternar divisao; `Super+Tab`: proxima janela
- Teclas de volume, microfone, brilho e midia: controles diretos
- `Super+1` a `Super+9`: trocar workspace; com `Shift`, mover a janela
- `Super+setas`: foco; com `Shift`, mover a janela

O painel Frutiger Aero tambem inclui luz noturna, nao perturbe, conexao de redes conhecidas/novas, pareamento de dispositivos, brilho, player, screenshot, launcher e sessao. A tela bloqueia apos 10 minutos de inatividade e apaga apos 15 minutos. Quando o globo e levado ao centro da tela, ele mostra os paises visiveis com continente e populacao estimada; essa camada fica oculta quando o globo esta na Waybar.

## Limpar configuracoes

Para apagar, sem backup, todas as configuracoes em `~/.config/hypr` e os diretórios de rice/painel relacionados, rode `./limpar.sh`. Isso tambem encerra os paineis ativos e remove os dados instalados em `~/.local/share/ultimadesk`; nao remove configuracoes de outros aplicativos, como terminal ou GTK. A pasta do Hyprland nao sera recriada: rode `./install.sh` depois para instalar o rice novamente.

## Requisitos

Hyprland em Arch Linux ou derivada com `pacman`. O centro de controle usa GTK 3; Wi-Fi e gerenciado pelo NetworkManager, Bluetooth pelo BlueZ e audio pelo PipeWire. A geracao do mapa interativo do globo pode ser ignorada quando o download dos dados geografico nao estiver disponivel; o restante do rice continua instalando.