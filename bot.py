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
    
    def extract_channel_id(self, url_or_id: str) -> str:
        """Extrai channel ID de uma URL ou retorna o ID se já estiver no formato correto"""
        # Se já é um channel ID válido
        if re.match(r'^UC[a-zA-Z0-9_-]{22}$', url_or_id):
            return url_or_id
        
        # Extrai de URLs do YouTube
        patterns = [
            r'youtube\.com/channel/([a-zA-Z0-9_-]+)',
            r'youtube\.com/c/([a-zA-Z0-9_-]+)',
            r'youtube\.com/@([a-zA-Z0-9_-]+)',
            r'youtube\.com/user/([a-zA-Z0-9_-]+)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url_or_id)
            if match:
                # Para URLs com /c/, /user/ ou @, precisamos converter para channel ID
                if '/channel/' in url_or_id:
                    return match.group(1)
                else:
                    # Tenta buscar o channel ID real via RSS
                    return self.get_channel_id_from_handle(match.group(1))
        
        # Se não encontrou padrão, tenta como handle direto
        return self.get_channel_id_from_handle(url_or_id)
    
    def get_channel_id_from_handle(self, handle: str) -> str:
        """Tenta obter channel ID a partir de um handle/username"""
        try:
            # Remove @ se presente
            handle = handle.lstrip('@')
            
            # Tenta diferentes formatos de RSS
            test_urls = [
                f"https://www.youtube.com/feeds/videos.xml?user={handle}",
                f"https://www.youtube.com/feeds/videos.xml?channel_id={handle}"
            ]
            
            for url in test_urls:
                try:
                    feed = feedparser.parse(url)
                    if feed.entries:
                        # Extrai channel ID do primeiro vídeo
                        for entry in feed.entries:
                            if hasattr(entry, 'yt_channelid'):
                                return entry.yt_channelid
                except:
                    continue
            
            return handle  # Retorna como está se não conseguir converter
        except:
            return handle
    
    def validate_channel_id(self, channel_id: str) -> bool:
        """Valida se um channel ID é válido testando o RSS"""
        try:
            rss_url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
            feed = feedparser.parse(rss_url)
            return len(feed.entries) > 0
        except:
            return False
    
    def get_channel_videos(self, channel_id: str) -> List[Dict]:
        """Busca vídeos recentes de um canal via RSS"""
        try:
            rss_url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
            feed = feedparser.parse(rss_url)
            
            videos = []
            for entry in feed.entries[:5]:  # Últimos 5 vídeos
                videos.append({
                    'video_id': entry.yt_videoid,
                    'title': entry.title,
                    'link': entry.link,
                    'published': entry.published,
                    'channel_name': entry.author
                })
            
            return videos
        except Exception as e:
            logger.error(f"Erro ao buscar vídeos do canal {channel_id}: {e}")
            return []
    
    def send_telegram_message(self, message: str, reply_markup=None):
        """Envia mensagem para o Telegram"""
        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            payload = {
                'chat_id': self.chat_id,
                'text': message,
                'parse_mode': 'HTML',
                'disable_web_page_preview': False
            }
            
            if reply_markup:
                payload['reply_markup'] = reply_markup
            
            response = requests.post(url, json=payload)
            if response.status_code == 200:
                logger.info("Mensagem enviada com sucesso!")
            else:
                logger.error(f"Erro ao enviar mensagem: {response.text}")
                
        except Exception as e:
            logger.error(f"Erro ao enviar mensagem: {e}")
    
    def get_telegram_updates(self):
        """Busca atualizações do Telegram"""
        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/getUpdates"
            params = {'offset': self.last_update_id + 1, 'timeout': 10}
            
            response = requests.get(url, params=params)
            if response.status_code == 200:
                data = response.json()
                return data.get('result', [])
            return []
        except Exception as e:
            logger.error(f"Erro ao buscar updates: {e}")
            return []
    
    def process_telegram_commands(self):
        """Processa comandos recebidos do Telegram"""
        updates = self.get_telegram_updates()
        
        for update in updates:
            self.last_update_id = update['update_id']
            
            if 'message' in update:
                message = update['message']
                text = message.get('text', '')
                
                # Verifica se é do chat correto
                if str(message['chat']['id']) != self.chat_id:
                    continue
                
                # Processa comandos
                if text.startswith('/'):
                    self.handle_command(text)
    
    def handle_command(self, command: str):
        """Processa comandos específicos"""
        parts = command.split()
        cmd = parts[0].lower()
        
        if cmd == '/start':
            self.cmd_start()
        elif cmd == '/help':
            self.cmd_help()
        elif cmd == '/list':
            self.cmd_list_channels()
        elif cmd == '/add':
            if len(parts) > 1:
                channel_input = ' '.join(parts[1:])
                self.cmd_add_channel(channel_input)
            else:
                self.send_telegram_message("❌ Use: /add [URL do canal ou Channel ID]")
        elif cmd == '/remove':
            if len(parts) > 1:
                channel_name = ' '.join(parts[1:])
                self.cmd_remove_channel(channel_name)
            else:
                self.send_telegram_message("❌ Use: /remove [nome do canal]")
        elif cmd == '/status':
            self.cmd_status()
        else:
            self.send_telegram_message("❌ Comando não reconhecido. Use /help para ver os comandos disponíveis.")
    
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

<b>Exemplo:</b>
/add https://youtube.com/c/felipe-deschamps
/add @felipedeschamps
/remove Felipe Deschamps

Pronto para começar! 🚀"""
        
        self.send_telegram_message(message)
    
    def cmd_help(self):
        """Comando /help"""
        self.cmd_start()
    
    def cmd_add_channel(self, channel_input: str):
        """Adiciona um canal para monitorar"""
        # Extrai channel ID
        channel_id = self.extract_channel_id(channel_input)
        
        if not channel_id:
            self.send_telegram_message("❌ Não consegui extrair o ID do canal. Verifique a URL.")
            return
        
        # Valida channel ID
        if not self.validate_channel_id(channel_id):
            self.send_telegram_message(f"❌ Canal inválido ou não encontrado: {channel_id}")
            return
        
        # Busca informações do canal
        videos = self.get_channel_videos(channel_id)
        if not videos:
            self.send_telegram_message("❌ Não consegui acessar os vídeos deste canal.")
            return
        
        channel_name = videos[0]['channel_name']
        
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
        
        self.send_telegram_message(f"✅ Canal <b>{channel_name}</b> adicionado com sucesso!\n\nID: {channel_id}")
    
    def cmd_remove_channel(self, channel_name: str):
        """Remove um canal"""
        channels = self.load_channels()
        
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
    
    def cmd_list_channels(self):
        """Lista canais monitorados"""
        channels = self.load_channels()
        
        if not channels:
            self.send_telegram_message("📭 Nenhum canal está sendo monitorado.\n\nUse /add [URL] para adicionar um canal.")
            return
        
        message = "📺 <b>Canais monitorados:</b>\n\n"
        
        for i, channel in enumerate(channels, 1):
            status = "✅" if channel.get('enabled', True) else "⏸️"
            message += f"{i}. {status} <b>{channel['name']}</b>\n"
            message += f"   ID: <code>{channel['channel_id']}</code>\n\n"
        
        message += f"Total: {len(channels)} canais"
        self.send_telegram_message(message)
    
    def cmd_status(self):
        """Mostra status do bot"""
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
    
    def format_video_message(self, video: Dict, channel_name: str) -> str:
        """Formata mensagem do vídeo para o Telegram"""
        return f"""🎥 <b>Novo vídeo no canal {channel_name}!</b>

📹 <b>{video['title']}</b>

🔗 <a href="{video['link']}">Assistir agora</a>

📅 {video['published']}"""
    
    def check_new_videos(self):
        """Verifica novos vídeos em todos os canais"""
        channels = self.load_channels()
        if not channels:
            return
        
        logger.info("Verificando novos vídeos...")
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
                    self.send_telegram_message(message)
                    
                    new_videos_found = True
            
            # Atualiza lista de vídeos conhecidos (mantém apenas os 10 mais recentes)
            current_video_ids = [v['video_id'] for v in videos]
            saved_data[channel_id]['last_video_ids'] = current_video_ids
            saved_data[channel_id]['channel_name'] = channel_name
        
        # Salva dados atualizados
        self.save_data(saved_data)
        
        if new_videos_found:
            logger.info(f"Enviadas notificações de novos vídeos!")
        else:
            logger.info("Nenhum vídeo novo encontrado.")
    
    async def run_forever(self):
        """Executa o bot continuamente"""
        logger.info("Bot iniciado! Monitorando canais e comandos...")
        
        # Envia mensagem de inicialização
        self.send_telegram_message("🤖 <b>Bot iniciado!</b>\n\nDigite /help para ver os comandos disponíveis.")
        
        while True:
            try:
                # Processa comandos do Telegram
                self.process_telegram_commands()
                
                # Verifica novos vídeos a cada 5 minutos
                await asyncio.sleep(300)
                self.check_new_videos()
                
            except Exception as e:
                logger.error(f"Erro no loop principal: {e}")
                await asyncio.sleep(60)

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