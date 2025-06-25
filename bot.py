import asyncio
import json
import os
import logging
import feedparser
import requests
import re
from datetime import datetime, timezone
from typing import List, Dict, Set

# Configuração de logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class YouTubeTelegramBot:
    def __init__(self):
        self.bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
        self.chat_id = os.getenv('CHAT_ID')
        self.data_file = 'videos_data.json'
        self.channels_file = 'channels.json'
        self.last_update_id = 0
        
        if not self.bot_token or not self.chat_id:
            raise ValueError("TELEGRAM_BOT_TOKEN e CHAT_ID devem estar definidos nas variáveis de ambiente")
        
        logger.info(f"Bot inicializado para chat ID: {self.chat_id}")
    
    def load_data(self) -> Dict:
        """Carrega dados dos últimos vídeos enviados"""
        try:
            with open(self.data_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            logger.info("Arquivo de dados não encontrado, criando novo...")
            return {}
    
    def save_data(self, data: Dict):
        """Salva dados dos últimos vídeos"""
        with open(self.data_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def load_channels(self) -> List[Dict]:
        """Carrega lista de canais para monitorar"""
        try:
            with open(self.channels_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            logger.info("Arquivo de canais não encontrado, criando novo...")
            return []
    
    def save_channels(self, channels: List[Dict]):
        """Salva lista de canais"""
        with open(self.channels_file, 'w', encoding='utf-8') as f:
            json.dump(channels, f, ensure_ascii=False, indent=2)
    
    def extract_channel_id_simple(self, input_text: str) -> str:
        """Extrai ou valida Channel ID - aceita apenas IDs diretos"""
        # Limpa a string
        input_text = input_text.strip()
        
        # Se já é um channel ID válido (UC + 22 caracteres)
        if re.match(r'^UC[a-zA-Z0-9_-]{22}
    
    def validate_channel_simple(self, channel_id: str) -> tuple:
        """Validação simples do canal - retorna (é_válido, nome_do_canal)"""
        try:
            rss_url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
            logger.info(f"Validando canal: {channel_id}")
            
            response = requests.get(rss_url, timeout=15)
            
            if response.status_code == 200:
                feed = feedparser.parse(response.content)
                
                if feed.entries and len(feed.entries) > 0:
                    channel_name = feed.entries[0].author if hasattr(feed.entries[0], 'author') else "Canal do YouTube"
                    logger.info(f"Canal válido: {channel_name}")
                    return True, channel_name
            
            logger.warning(f"Canal inválido ou sem vídeos: {channel_id}")
            return False, None
            
        except Exception as e:
            logger.error(f"Erro na validação: {e}")
            return False, None
    
    def get_channel_videos(self, channel_id: str) -> List[Dict]:
        """Busca vídeos recentes de um canal via RSS"""
        try:
            rss_url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
            response = requests.get(rss_url, timeout=15)
            
            if response.status_code != 200:
                return []
            
            feed = feedparser.parse(response.content)
            
            videos = []
            for entry in feed.entries[:5]:  # Últimos 5 vídeos
                videos.append({
                    'video_id': entry.yt_videoid if hasattr(entry, 'yt_videoid') else entry.id.split(':')[-1],
                    'title': entry.title,
                    'link': entry.link,
                    'published': entry.published,
                    'channel_name': entry.author if hasattr(entry, 'author') else "Canal do YouTube"
                })
            
            return videos
            
        except Exception as e:
            logger.error(f"Erro ao buscar vídeos do canal {channel_id}: {e}")
            return []
    
    def send_telegram_message(self, message: str):
        """Envia mensagem para o Telegram"""
        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            payload = {
                'chat_id': self.chat_id,
                'text': message,
                'parse_mode': 'HTML',
                'disable_web_page_preview': False
            }
            
            response = requests.post(url, json=payload, timeout=10)
            
            if response.status_code == 200:
                logger.info("Mensagem enviada com sucesso!")
                return True
            else:
                logger.error(f"Erro ao enviar mensagem: {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Erro ao enviar mensagem: {e}")
            return False
    
    def get_telegram_updates(self):
        """Busca atualizações do Telegram"""
        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/getUpdates"
            params = {'offset': self.last_update_id + 1, 'timeout': 2}
            
            response = requests.get(url, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                return data.get('result', [])
            else:
                logger.warning(f"Erro ao buscar updates: {response.status_code}")
                return []
                
        except Exception as e:
            logger.error(f"Erro ao buscar updates: {e}")
            return []
    
    def process_telegram_commands(self):
        """Processa comandos recebidos do Telegram"""
        updates = self.get_telegram_updates()
        
        for update in updates:
            try:
                self.last_update_id = update['update_id']
                
                if 'message' in update:
                    message = update['message']
                    text = message.get('text', '').strip()
                    chat_id = str(message['chat']['id'])
                    
                    logger.info(f"Mensagem recebida: '{text}' do chat: {chat_id}")
                    
                    # Verifica se é do chat correto
                    if chat_id != self.chat_id:
                        logger.warning(f"Mensagem de chat incorreto: {chat_id} != {self.chat_id}")
                        continue
                    
                    # Processa comandos
                    if text.startswith('/'):
                        logger.info(f"Processando comando: {text}")
                        self.handle_command(text)
                    
            except Exception as e:
                logger.error(f"Erro ao processar update: {e}")
                continue
    
    def handle_command(self, command: str):
        """Processa comandos específicos"""
        try:
            parts = command.split(None, 1)  # Divide em no máximo 2 partes
            cmd = parts[0].lower()
            
            logger.info(f"Comando recebido: {cmd}")
            
            if cmd == '/start':
                self.cmd_start()
            elif cmd == '/help':
                self.cmd_help()
            elif cmd == '/list':
                self.cmd_list_channels()
            elif cmd == '/add':
                if len(parts) > 1:
                    self.cmd_add_channel(parts[1])
                else:
                    self.send_telegram_message("❌ Use: /add [Channel ID]\n\nExemplo: /add UCU5JicSrEM5A63jkJ2QvGYw\n\nDigite /help para ver como encontrar o Channel ID.")
            elif cmd == '/remove':
                if len(parts) > 1:
                    self.cmd_remove_channel(parts[1])
                else:
                    self.send_telegram_message("❌ Use: /remove [nome do canal]")
            elif cmd == '/status':
                self.cmd_status()
            else:
                self.send_telegram_message("❌ Comando não reconhecido. Use /help para ver os comandos disponíveis.")
                
        except Exception as e:
            logger.error(f"Erro ao processar comando {command}: {e}")
            self.send_telegram_message("❌ Erro interno. Tente novamente em alguns segundos.")
    
    def cmd_start(self):
        """Comando /start"""
        message = """🤖 <b>YouTube Telegram Bot</b>

Olá! Eu monitoro canais do YouTube e te aviso quando há novos vídeos.

<b>⚡ IMPORTANTE:</b> Eu só notífico sobre vídeos publicados APÓS você adicionar o canal (não de vídeos antigos).

<b>Comandos disponíveis:</b>
/help - Mostra esta ajuda
/add [Channel ID] - Adiciona um canal para monitorar
/remove [nome] - Remove um canal
/list - Lista canais monitorados
/status - Status do bot

<b>⚠️ IMPORTANTE: Use o Channel ID (formato UC...)</b>

<b>📺 Como encontrar o Channel ID:</b>

<b>Método 1 - URL direta:</b>
Se a URL for: youtube.com/channel/UCxxxx
→ Copie: UCxxxx

<b>Método 2 - Via qualquer vídeo:</b>
1. Abra qualquer vídeo do canal
2. Clique no nome do canal
3. Na URL que abrir, copie o UCxxxx

<b>Método 3 - Código fonte:</b>
1. Vá no canal
2. Clique com botão direito → "Ver código fonte"
3. Ctrl+F → "channelId"
4. Copie o UCxxxx

<b>Exemplo:</b>
/add UCU5JicSrEM5A63jkJ2QvGYw

🎯 Vídeos atuais são marcados como "já vistos" automaticamente!

Pronto para começar! 🚀"""
        
        self.send_telegram_message(message)
    
    def cmd_help(self):
        """Comando /help"""
        self.cmd_start()
    
    def cmd_add_channel(self, channel_input: str):
        """Adiciona um canal para monitorar"""
        try:
            self.send_telegram_message("🔍 Validando Channel ID...")
            
            # Extrai/valida channel ID
            logger.info(f"Processando entrada: {channel_input}")
            channel_id = self.extract_channel_id_simple(channel_input)
            
            if not channel_id:
                self.send_telegram_message("""❌ <b>Formato inválido!</b>

🎯 <b>Use o Channel ID (formato UCxxxx)</b>

📺 <b>Como encontrar o Channel ID:</b>

<b>Método 1:</b> URL direta
youtube.com/channel/UCxxxx → copie UCxxxx

<b>Método 2:</b> Via vídeo
1. Abra qualquer vídeo do canal
2. Clique no nome do canal  
3. Na URL, copie o UCxxxx

<b>Exemplo:</b>
/add UCU5JicSrEM5A63jkJ2QvGYw""")
                return
            
            logger.info(f"Channel ID a ser validado: {channel_id}")
            
            # Valida canal
            is_valid, channel_name = self.validate_channel_simple(channel_id)
            
            if not is_valid:
                self.send_telegram_message(f"""❌ <b>Channel ID inválido ou canal sem vídeos públicos</b>

🆔 ID testado: <code>{channel_id}</code>

✅ <b>Verifique se:</b>
• O Channel ID está correto (formato UCxxxx)
• O canal existe e tem vídeos públicos
• Você copiou o ID completo

💡 <b>Dica:</b> Teste primeiro acessar:
youtube.com/channel/{channel_id}""")
                return
            
            # Carrega canais existentes
            channels = self.load_channels()
            
            # Verifica se já existe
            for channel in channels:
                if channel['channel_id'] == channel_id:
                    self.send_telegram_message(f"⚠️ Canal <b>{channel_name}</b> já está sendo monitorado!")
                    return
            
            # Busca vídeos atuais para marcar como "já vistos"
            self.send_telegram_message("🔄 Configurando monitoramento (marcando vídeos atuais como já vistos)...")
            
            current_videos = self.get_channel_videos(channel_id)
            if current_videos:
                # Salva os vídeos atuais como já processados (SEM enviar notificações)
                saved_data = self.load_data()
                current_video_ids = [v['video_id'] for v in current_videos]
                
                saved_data[channel_id] = {
                    'last_video_ids': current_video_ids,
                    'channel_name': channel_name
                }
                
                self.save_data(saved_data)
                logger.info(f"Marcados {len(current_video_ids)} vídeos existentes como já vistos para o canal {channel_name}")
            
            # Adiciona novo canal
            new_channel = {
                'name': channel_name,
                'channel_id': channel_id,
                'enabled': True,
                'added_date': datetime.now().isoformat()
            }
            
            channels.append(new_channel)
            self.save_channels(channels)
            
            video_count = len(current_videos) if current_videos else 0
            
            self.send_telegram_message(f"""✅ <b>Canal adicionado com sucesso!</b>

📺 <b>Nome:</b> {channel_name}
🆔 <b>ID:</b> <code>{channel_id}</code>
📹 <b>Vídeos atuais:</b> {video_count} (marcados como já vistos)

🔔 <b>A partir de agora você receberá notificações APENAS dos novos vídeos!</b>
⏱️ Verificação: a cada 1 minuto""")
            
        except Exception as e:
            logger.error(f"Erro ao adicionar canal: {e}")
            self.send_telegram_message(f"❌ Erro interno ao adicionar canal.\n\nTente novamente em alguns segundos.")
    
    def cmd_remove_channel(self, channel_name: str):
        """Remove um canal"""
        try:
            channels = self.load_channels()
            
            if not channels:
                self.send_telegram_message("📭 Nenhum canal está sendo monitorado.")
                return
            
            # Busca canal por nome (case insensitive)
            found_channel = None
            for i, channel in enumerate(channels):
                if channel_name.lower() in channel['name'].lower():
                    found_channel = (i, channel)
                    break
            
            if not found_channel:
                self.send_telegram_message(f"❌ Canal '{channel_name}' não encontrado.\n\nUse /list para ver os canais monitorados.")
                return
            
            index, channel = found_channel
            removed_name = channel['name']
            
            # Remove canal
            channels.pop(index)
            self.save_channels(channels)
            
            self.send_telegram_message(f"✅ Canal <b>{removed_name}</b> removido com sucesso!")
            
        except Exception as e:
            logger.error(f"Erro ao remover canal: {e}")
            self.send_telegram_message("❌ Erro ao remover canal. Tente novamente.")
    
    def cmd_list_channels(self):
        """Lista canais monitorados"""
        try:
            channels = self.load_channels()
            
            if not channels:
                self.send_telegram_message("📭 Nenhum canal está sendo monitorado.\n\nUse /add [Channel ID] para adicionar um canal.\n\nDigite /help para ver como encontrar o Channel ID.")
                return
            
            message = "📺 <b>Canais monitorados:</b>\n\n"
            
            for i, channel in enumerate(channels, 1):
                status = "✅" if channel.get('enabled', True) else "⏸️"
                message += f"{i}. {status} <b>{channel['name']}</b>\n"
                message += f"   <code>{channel['channel_id']}</code>\n\n"
            
            message += f"Total: {len(channels)} canais"
            self.send_telegram_message(message)
            
        except Exception as e:
            logger.error(f"Erro ao listar canais: {e}")
            self.send_telegram_message("❌ Erro ao listar canais.")
    
    def cmd_status(self):
        """Mostra status do bot"""
        try:
            channels = self.load_channels()
            data = self.load_data()
            
            enabled_channels = sum(1 for c in channels if c.get('enabled', True))
            total_videos_tracked = sum(len(d.get('last_video_ids', [])) for d in data.values())
            
            message = f"""📊 <b>Status do Bot</b>

🎯 <b>Canais monitorados:</b> {enabled_channels}/{len(channels)}
📹 <b>Vídeos rastreados:</b> {total_videos_tracked}
🔄 <b>Verificação:</b> A cada 1 minuto
✅ <b>Status:</b> Ativo

<b>Última verificação:</b> {datetime.now().strftime('%d/%m/%Y %H:%M')}

⚡ <b>Responsividade:</b> Comandos processados a cada 5 segundos"""
            
            self.send_telegram_message(message)
            
        except Exception as e:
            logger.error(f"Erro ao mostrar status: {e}")
            self.send_telegram_message("❌ Erro ao mostrar status.")
    
    def format_video_message(self, video: Dict, channel_name: str) -> str:
        """Formata mensagem do vídeo para o Telegram"""
        return f"""🎥 <b>Novo vídeo no canal {channel_name}!</b>

📹 <b>{video['title']}</b>

🔗 <a href="{video['link']}">Assistir agora</a>

📅 {video['published']}"""
    
    def check_new_videos(self):
        """Verifica novos vídeos em todos os canais"""
        try:
            channels = self.load_channels()
            if not channels:
                logger.info("Nenhum canal para verificar")
                return
            
            logger.info(f"Verificando {len(channels)} canais...")
            saved_data = self.load_data()
            new_videos_found = False
            
            for channel in channels:
                if not channel.get('enabled', True):
                    continue
                    
                channel_id = channel['channel_id']
                channel_name = channel['name']
                
                logger.info(f"Verificando canal: {channel_name}")
                
                videos = self.get_channel_videos(channel_id)
                if not videos:
                    logger.warning(f"Nenhum vídeo encontrado para {channel_name}")
                    continue
                
                # Verifica se já temos dados deste canal
                if channel_id not in saved_data:
                    # Canal novo - isso não deveria acontecer se foi adicionado corretamente
                    logger.warning(f"Canal {channel_name} não tem dados salvos, pulando primeira verificação")
                    saved_data[channel_id] = {
                        'last_video_ids': [v['video_id'] for v in videos],
                        'channel_name': channel_name
                    }
                    continue
                
                last_video_ids = set(saved_data[channel_id]['last_video_ids'])
                
                # Verifica novos vídeos (só os que NÃO estão na lista de já vistos)
                new_videos_in_this_channel = []
                for video in videos:
                    if video['video_id'] not in last_video_ids:
                        new_videos_in_this_channel.append(video)
                        logger.info(f"🎬 NOVO VÍDEO encontrado: {video['title']} - Canal: {channel_name}")
                
                # Envia notificações apenas dos vídeos realmente novos
                for video in new_videos_in_this_channel:
                    message = self.format_video_message(video, channel_name)
                    if self.send_telegram_message(message):
                        new_videos_found = True
                        logger.info(f"✅ Notificação enviada: {video['title']}")
                
                # Atualiza lista de vídeos conhecidos (mantém apenas os 10 mais recentes)
                current_video_ids = [v['video_id'] for v in videos]
                saved_data[channel_id]['last_video_ids'] = current_video_ids
                saved_data[channel_id]['channel_name'] = channel_name
                
                if new_videos_in_this_channel:
                    logger.info(f"📊 Canal {channel_name}: {len(new_videos_in_this_channel)} novos vídeos processados")
                else:
                    logger.info(f"📊 Canal {channel_name}: nenhum vídeo novo")
            
            # Salva dados atualizados
            self.save_data(saved_data)
            
            if new_videos_found:
                logger.info("🎉 Enviadas notificações de novos vídeos!")
            else:
                logger.info("😴 Nenhum vídeo novo encontrado em nenhum canal.")
                
        except Exception as e:
            logger.error(f"Erro na verificação de vídeos: {e}")
    
    async def run_forever(self):
        """Executa o bot continuamente"""
        logger.info("Bot iniciado! Monitorando canais e comandos...")
        
        # Envia mensagem de inicialização
        self.send_telegram_message("🤖 <b>Bot iniciado e funcionando!</b>\n\n⏱️ <b>Verificação:</b> A cada 1 minuto\n\nDigite /help para ver como adicionar canais.")
        
        # Contador para verificação de vídeos (a cada 1 minuto = 12 ciclos de 5 segundos)
        video_check_counter = 0
        
        while True:
            try:
                # Processa comandos a cada 5 segundos (mais responsivo)
                self.process_telegram_commands()
                
                # Verifica novos vídeos a cada 1 minuto (12 ciclos de 5 segundos)
                video_check_counter += 1
                if video_check_counter >= 12:
                    self.check_new_videos()
                    video_check_counter = 0
                
                await asyncio.sleep(5)  # 5 segundos entre verificações de comandos
                
            except Exception as e:
                logger.error(f"Erro no loop principal: {e}")
                await asyncio.sleep(30)

def main():
    """Função principal"""
    try:
        bot = YouTubeTelegramBot()
        asyncio.run(bot.run_forever())
    except KeyboardInterrupt:
        logger.info("Bot interrompido pelo usuário")
    except Exception as e:
        logger.error(f"Erro fatal: {e}")

if __name__ == "__main__":
    main(), input_text):
            logger.info(f"Channel ID válido detectado: {input_text}")
            return input_text
        
        # Tenta extrair de URL se ainda contém /channel/
        channel_match = re.search(r'youtube\.com/channel/([UC][a-zA-Z0-9_-]{22})', input_text)
        if channel_match:
            channel_id = channel_match.group(1)
            logger.info(f"Channel ID extraído de URL: {channel_id}")
            return channel_id
        
        # Se não é um formato reconhecido, retorna None
        logger.warning(f"Formato não reconhecido: {input_text}")
        return None
    
    def handle_to_channel_id(self, handle: str) -> str:
        """Converte handle/username para channel ID via múltiplos métodos"""
        logger.info(f"Tentando converter handle: {handle}")
        
        # Método 1: Tentar via RSS direto
        rss_attempts = [
            f"https://www.youtube.com/feeds/videos.xml?user={handle}",
            f"https://www.youtube.com/feeds/videos.xml?channel_id={handle}"
        ]
        
        for rss_url in rss_attempts:
            try:
                logger.info(f"Testando RSS: {rss_url}")
                response = requests.get(rss_url, timeout=10)
                
                if response.status_code == 200:
                    feed = feedparser.parse(response.content)
                    
                    if feed.entries:
                        for entry in feed.entries:
                            if hasattr(entry, 'yt_channelid'):
                                logger.info(f"Channel ID encontrado via RSS: {entry.yt_channelid}")
                                return entry.yt_channelid
                        
                        if feed.entries[0].link:
                            channel_match = re.search(r'channel/([UC][a-zA-Z0-9_-]{22})', feed.entries[0].link)
                            if channel_match:
                                logger.info(f"Channel ID extraído do link RSS: {channel_match.group(1)}")
                                return channel_match.group(1)
                            
            except Exception as e:
                logger.warning(f"Erro ao testar RSS {rss_url}: {e}")
                continue
        
        # Método 2: Web scraping da página do canal
        try:
            logger.info(f"Tentando web scraping para {handle}")
            
            # URLs possíveis para tentar
            urls_to_try = [
                f"https://www.youtube.com/c/{handle}",
                f"https://www.youtube.com/@{handle}",
                f"https://www.youtube.com/user/{handle}"
            ]
            
            for url in urls_to_try:
                try:
                    logger.info(f"Fazendo scraping de: {url}")
                    headers = {
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                    }
                    
                    response = requests.get(url, headers=headers, timeout=15)
                    
                    if response.status_code == 200:
                        content = response.text
                        
                        # Procura por padrões de channel ID no HTML
                        patterns = [
                            r'"channelId":"([UC][a-zA-Z0-9_-]{22})"',
                            r'"browseId":"([UC][a-zA-Z0-9_-]{22})"',
                            r'channel/([UC][a-zA-Z0-9_-]{22})',
                            r'"externalId":"([UC][a-zA-Z0-9_-]{22})"'
                        ]
                        
                        for pattern in patterns:
                            match = re.search(pattern, content)
                            if match:
                                channel_id = match.group(1)
                                logger.info(f"Channel ID encontrado via scraping: {channel_id}")
                                return channel_id
                
                except Exception as e:
                    logger.warning(f"Erro no scraping de {url}: {e}")
                    continue
                    
        except Exception as e:
            logger.warning(f"Erro geral no web scraping: {e}")
        
        # Método 3: Tentar usando o próprio handle como fallback
        logger.warning(f"Não conseguiu converter {handle}, usando como está")
        return handle
    
    def validate_channel_simple(self, channel_id: str) -> tuple:
        """Validação simples do canal - retorna (é_válido, nome_do_canal)"""
        try:
            rss_url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
            logger.info(f"Validando canal: {channel_id}")
            
            response = requests.get(rss_url, timeout=15)
            
            if response.status_code == 200:
                feed = feedparser.parse(response.content)
                
                if feed.entries and len(feed.entries) > 0:
                    channel_name = feed.entries[0].author if hasattr(feed.entries[0], 'author') else "Canal do YouTube"
                    logger.info(f"Canal válido: {channel_name}")
                    return True, channel_name
            
            logger.warning(f"Canal inválido ou sem vídeos: {channel_id}")
            return False, None
            
        except Exception as e:
            logger.error(f"Erro na validação: {e}")
            return False, None
    
    def get_channel_videos(self, channel_id: str) -> List[Dict]:
        """Busca vídeos recentes de um canal via RSS"""
        try:
            rss_url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
            response = requests.get(rss_url, timeout=15)
            
            if response.status_code != 200:
                return []
            
            feed = feedparser.parse(response.content)
            
            videos = []
            for entry in feed.entries[:5]:  # Últimos 5 vídeos
                videos.append({
                    'video_id': entry.yt_videoid if hasattr(entry, 'yt_videoid') else entry.id.split(':')[-1],
                    'title': entry.title,
                    'link': entry.link,
                    'published': entry.published,
                    'channel_name': entry.author if hasattr(entry, 'author') else "Canal do YouTube"
                })
            
            return videos
            
        except Exception as e:
            logger.error(f"Erro ao buscar vídeos do canal {channel_id}: {e}")
            return []
    
    def send_telegram_message(self, message: str):
        """Envia mensagem para o Telegram"""
        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            payload = {
                'chat_id': self.chat_id,
                'text': message,
                'parse_mode': 'HTML',
                'disable_web_page_preview': False
            }
            
            response = requests.post(url, json=payload, timeout=10)
            
            if response.status_code == 200:
                logger.info("Mensagem enviada com sucesso!")
                return True
            else:
                logger.error(f"Erro ao enviar mensagem: {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Erro ao enviar mensagem: {e}")
            return False
    
    def get_telegram_updates(self):
        """Busca atualizações do Telegram"""
        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/getUpdates"
            params = {'offset': self.last_update_id + 1, 'timeout': 2}
            
            response = requests.get(url, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                return data.get('result', [])
            else:
                logger.warning(f"Erro ao buscar updates: {response.status_code}")
                return []
                
        except Exception as e:
            logger.error(f"Erro ao buscar updates: {e}")
            return []
    
    def process_telegram_commands(self):
        """Processa comandos recebidos do Telegram"""
        updates = self.get_telegram_updates()
        
        for update in updates:
            try:
                self.last_update_id = update['update_id']
                
                if 'message' in update:
                    message = update['message']
                    text = message.get('text', '').strip()
                    chat_id = str(message['chat']['id'])
                    
                    logger.info(f"Mensagem recebida: '{text}' do chat: {chat_id}")
                    
                    # Verifica se é do chat correto
                    if chat_id != self.chat_id:
                        logger.warning(f"Mensagem de chat incorreto: {chat_id} != {self.chat_id}")
                        continue
                    
                    # Processa comandos
                    if text.startswith('/'):
                        logger.info(f"Processando comando: {text}")
                        self.handle_command(text)
                    
            except Exception as e:
                logger.error(f"Erro ao processar update: {e}")
                continue
    
    def handle_command(self, command: str):
        """Processa comandos específicos"""
        try:
            parts = command.split(None, 1)  # Divide em no máximo 2 partes
            cmd = parts[0].lower()
            
            logger.info(f"Comando recebido: {cmd}")
            
            if cmd == '/start':
                self.cmd_start()
            elif cmd == '/help':
                self.cmd_help()
            elif cmd == '/list':
                self.cmd_list_channels()
            elif cmd == '/add':
                if len(parts) > 1:
                    self.cmd_add_channel(parts[1])
                else:
                    self.send_telegram_message("❌ Use: /add [URL do canal]\n\nExemplo: /add https://youtube.com/@felipedeschamps")
            elif cmd == '/remove':
                if len(parts) > 1:
                    self.cmd_remove_channel(parts[1])
                else:
                    self.send_telegram_message("❌ Use: /remove [nome do canal]")
            elif cmd == '/status':
                self.cmd_status()
            else:
                self.send_telegram_message("❌ Comando não reconhecido. Use /help para ver os comandos disponíveis.")
                
        except Exception as e:
            logger.error(f"Erro ao processar comando {command}: {e}")
            self.send_telegram_message("❌ Erro interno. Tente novamente em alguns segundos.")
    
    def cmd_start(self):
        """Comando /start"""
        message = """🤖 <b>YouTube Telegram Bot</b>

Olá! Eu monitoro canais do YouTube e te aviso quando há novos vídeos.

<b>Comandos disponíveis:</b>
/help - Mostra esta ajuda
/add [URL] - Adiciona um canal para monitorar
/remove [nome] - Remove um canal
/list - Lista canais monitorados
/status - Status do bot

<b>Exemplos:</b>
/add https://youtube.com/@felipedeschamps
/add @programadorbr
/remove Felipe Deschamps

Pronto para começar! 🚀"""
        
        self.send_telegram_message(message)
    
    def cmd_help(self):
        """Comando /help"""
        self.cmd_start()
    
    def cmd_add_channel(self, channel_input: str):
        """Adiciona um canal para monitorar"""
        try:
            self.send_telegram_message("🔍 Processando canal... Isso pode levar até 30 segundos.")
            
            # Extrai channel ID
            logger.info(f"Processando entrada: {channel_input}")
            channel_id = self.extract_channel_id_simple(channel_input)
            logger.info(f"Channel ID extraído: {channel_id}")
            
            if not channel_id:
                self.send_telegram_message("❌ Não consegui extrair o ID do canal. Verifique a URL.")
                return
            
            # Feedback para o usuário
            self.send_telegram_message(f"🔄 Tentando validar canal com ID: <code>{channel_id}</code>")
            
            # Valida canal
            is_valid, channel_name = self.validate_channel_simple(channel_id)
            
            if not is_valid:
                # Se a validação falhou, tenta métodos alternativos
                logger.info("Validação inicial falhou, tentando métodos alternativos...")
                self.send_telegram_message("🔄 Primeira tentativa falhou, testando métodos alternativos...")
                
                # Tenta extrair novamente com web scraping se a entrada original era uma URL
                if 'youtube.com' in channel_input.lower():
                    # Extrai handle da URL original
                    url_patterns = [
                        r'youtube\.com/c/([^/?&\s]+)',
                        r'youtube\.com/@([^/?&\s]+)',
                        r'youtube\.com/user/([^/?&\s]+)'
                    ]
                    
                    for pattern in url_patterns:
                        match = re.search(pattern, channel_input)
                        if match:
                            handle = match.group(1)
                            logger.info(f"Tentando web scraping para handle: {handle}")
                            alternative_id = self.handle_to_channel_id(handle)
                            
                            if alternative_id != handle:  # Se conseguiu converter
                                logger.info(f"Método alternativo encontrou: {alternative_id}")
                                is_valid, channel_name = self.validate_channel_simple(alternative_id)
                                if is_valid:
                                    channel_id = alternative_id
                                    break
                
                # Se ainda não conseguiu, tenta o fallback final
                if not is_valid:
                    self.send_telegram_message(f"❌ Canal não encontrado.\n\n📝 <b>Informações para debug:</b>\nURL original: {channel_input}\nID testado: <code>{channel_id}</code>\n\n💡 <b>Dicas:</b>\n• Tente usar o formato @usuario\n• Ou copie a URL completa do canal\n• Verifique se o canal existe e tem vídeos públicos")
                    return
            
            # Carrega canais existentes
            channels = self.load_channels()
            
            # Verifica se já existe
            for channel in channels:
                if channel['channel_id'] == channel_id:
                    self.send_telegram_message(f"⚠️ Canal <b>{channel_name}</b> já está sendo monitorado!")
                    return
            
            # Adiciona novo canal
            new_channel = {
                'name': channel_name,
                'channel_id': channel_id,
                'enabled': True,
                'added_date': datetime.now().isoformat()
            }
            
            channels.append(new_channel)
            self.save_channels(channels)
            
            self.send_telegram_message(f"✅ <b>Canal adicionado com sucesso!</b>\n\n📺 <b>Nome:</b> {channel_name}\n🆔 <b>ID:</b> <code>{channel_id}</code>\n\nAgora você receberá notificações dos novos vídeos! 🎉")
            
        except Exception as e:
            logger.error(f"Erro ao adicionar canal: {e}")
            self.send_telegram_message(f"❌ Erro interno ao adicionar canal.\n\nDetalhes técnicos: {str(e)[:100]}")
    
    def cmd_remove_channel(self, channel_name: str):
        """Remove um canal"""
        try:
            channels = self.load_channels()
            
            if not channels:
                self.send_telegram_message("📭 Nenhum canal está sendo monitorado.")
                return
            
            # Busca canal por nome (case insensitive)
            found_channel = None
            for i, channel in enumerate(channels):
                if channel_name.lower() in channel['name'].lower():
                    found_channel = (i, channel)
                    break
            
            if not found_channel:
                self.send_telegram_message(f"❌ Canal '{channel_name}' não encontrado.\n\nUse /list para ver os canais monitorados.")
                return
            
            index, channel = found_channel
            removed_name = channel['name']
            
            # Remove canal
            channels.pop(index)
            self.save_channels(channels)
            
            self.send_telegram_message(f"✅ Canal <b>{removed_name}</b> removido com sucesso!")
            
        except Exception as e:
            logger.error(f"Erro ao remover canal: {e}")
            self.send_telegram_message("❌ Erro ao remover canal. Tente novamente.")
    
    def cmd_list_channels(self):
        """Lista canais monitorados"""
        try:
            channels = self.load_channels()
            
            if not channels:
                self.send_telegram_message("📭 Nenhum canal está sendo monitorado.\n\nUse /add [URL] para adicionar um canal.")
                return
            
            message = "📺 <b>Canais monitorados:</b>\n\n"
            
            for i, channel in enumerate(channels, 1):
                status = "✅" if channel.get('enabled', True) else "⏸️"
                message += f"{i}. {status} <b>{channel['name']}</b>\n"
                message += f"   <code>{channel['channel_id']}</code>\n\n"
            
            message += f"Total: {len(channels)} canais"
            self.send_telegram_message(message)
            
        except Exception as e:
            logger.error(f"Erro ao listar canais: {e}")
            self.send_telegram_message("❌ Erro ao listar canais.")
    
    def cmd_status(self):
        """Mostra status do bot"""
        try:
            channels = self.load_channels()
            data = self.load_data()
            
            enabled_channels = sum(1 for c in channels if c.get('enabled', True))
            total_videos_tracked = sum(len(d.get('last_video_ids', [])) for d in data.values())
            
            message = f"""📊 <b>Status do Bot</b>

🎯 <b>Canais monitorados:</b> {enabled_channels}/{len(channels)}
📹 <b>Vídeos rastreados:</b> {total_videos_tracked}
🔄 <b>Verificação:</b> A cada 5 minutos
✅ <b>Status:</b> Ativo

<b>Última verificação:</b> {datetime.now().strftime('%d/%m/%Y %H:%M')}"""
            
            self.send_telegram_message(message)
            
        except Exception as e:
            logger.error(f"Erro ao mostrar status: {e}")
            self.send_telegram_message("❌ Erro ao mostrar status.")
    
    def format_video_message(self, video: Dict, channel_name: str) -> str:
        """Formata mensagem do vídeo para o Telegram"""
        return f"""🎥 <b>Novo vídeo no canal {channel_name}!</b>

📹 <b>{video['title']}</b>

🔗 <a href="{video['link']}">Assistir agora</a>

📅 {video['published']}"""
    
    def check_new_videos(self):
        """Verifica novos vídeos em todos os canais"""
        try:
            channels = self.load_channels()
            if not channels:
                logger.info("Nenhum canal para verificar")
                return
            
            logger.info(f"Verificando {len(channels)} canais...")
            saved_data = self.load_data()
            new_videos_found = False
            
            for channel in channels:
                if not channel.get('enabled', True):
                    continue
                    
                channel_id = channel['channel_id']
                channel_name = channel['name']
                
                logger.info(f"Verificando canal: {channel_name}")
                
                videos = self.get_channel_videos(channel_id)
                if not videos:
                    logger.warning(f"Nenhum vídeo encontrado para {channel_name}")
                    continue
                
                # Verifica se já temos dados deste canal
                if channel_id not in saved_data:
                    saved_data[channel_id] = {
                        'last_video_ids': [],
                        'channel_name': channel_name
                    }
                
                last_video_ids = set(saved_data[channel_id]['last_video_ids'])
                
                # Verifica novos vídeos
                for video in videos:
                    if video['video_id'] not in last_video_ids:
                        logger.info(f"Novo vídeo encontrado: {video['title']}")
                        
                        # Envia notificação
                        message = self.format_video_message(video, channel_name)
                        if self.send_telegram_message(message):
                            new_videos_found = True
                
                # Atualiza lista de vídeos conhecidos (mantém apenas os 10 mais recentes)
                current_video_ids = [v['video_id'] for v in videos]
                saved_data[channel_id]['last_video_ids'] = current_video_ids
                saved_data[channel_id]['channel_name'] = channel_name
            
            # Salva dados atualizados
            self.save_data(saved_data)
            
            if new_videos_found:
                logger.info("Enviadas notificações de novos vídeos!")
            else:
                logger.info("Nenhum vídeo novo encontrado.")
                
        except Exception as e:
            logger.error(f"Erro na verificação de vídeos: {e}")
    
    async def run_forever(self):
        """Executa o bot continuamente"""
        logger.info("Bot iniciado! Monitorando canais e comandos...")
        
        # Envia mensagem de inicialização
        self.send_telegram_message("🤖 <b>Bot iniciado e funcionando!</b>\n\nDigite /help para ver os comandos disponíveis.")
        
        # Contador para verificação de vídeos
        video_check_counter = 0
        
        while True:
            try:
                # Processa comandos a cada 5 segundos
                self.process_telegram_commands()
                
                # Verifica novos vídeos a cada 5 minutos (60 ciclos de 5 segundos)
                video_check_counter += 1
                if video_check_counter >= 60:
                    self.check_new_videos()
                    video_check_counter = 0
                
                await asyncio.sleep(5)  # 5 segundos entre verificações
                
            except Exception as e:
                logger.error(f"Erro no loop principal: {e}")
                await asyncio.sleep(30)

def main():
    """Função principal"""
    try:
        bot = YouTubeTelegramBot()
        asyncio.run(bot.run_forever())
    except KeyboardInterrupt:
        logger.info("Bot interrompido pelo usuário")
    except Exception as e:
        logger.error(f"Erro fatal: {e}")

if __name__ == "__main__":
    main()
