import discord
from discord.ext import commands
import json
import os
from dotenv import load_dotenv
from flask import Flask
import threading
from discord import app_commands

# Charger les variables d'environnement
load_dotenv()

# Configuration des intents
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix="/", intents=intents)

# Initialisation de Flask pour maintenir le bot actif
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is alive!"

def run_flask():
    app.run(host='0.0.0.0', port=8080)

flask_thread = threading.Thread(target=run_flask)
flask_thread.start()

# Fichier pour stocker les avis et la configuration
AVIS_FILE = "avis.json"
CONFIG_FILE = "config.json"

# Charger les avis existants (Sécurisé)
def load_avis():
    if os.path.exists(AVIS_FILE):
        try:
            with open(AVIS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError:
            print(f"⚠️ Erreur de lecture dans {AVIS_FILE}, réinitialisation...")
            return {}
    return {}

def save_avis(avis):
    with open(AVIS_FILE, "w", encoding="utf-8") as f:
        json.dump(avis, f, indent=4, ensure_ascii=False)

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError:
            print(f"⚠️ Erreur de lecture dans {CONFIG_FILE}, réinitialisation...")
            return {"roles_staff": []}
    return {"roles_staff": []}

def save_config(config):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=4, ensure_ascii=False)

avis_data = load_avis()
config = load_config()

def est_staff(member: discord.Member) -> bool:
    return any(role.id in config["roles_staff"] for role in member.roles)

@bot.event
async def on_ready():
    print(f"Bot connecté en tant que {bot.user}")
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} command(s)")
    except Exception as e:
        print(e)


# ─── SYSTÈME DE FORMULAIRE (MODAL) ───

class AvisModal(discord.ui.Modal, title="Formulaire d'avis Staff"):
    # Champs du formulaire
    staff_input = discord.ui.TextInput(
        label="Nom ou Pseudo du Staff",
        placeholder="Ex: Jean / @Jean (sans le @)",
        required=True,
        max_length=50
    )
    note_input = discord.ui.TextInput(
        label="Note (Chiffre de 1 à 5)",
        placeholder="Ex: 5",
        required=True,
        min_length=1,
        max_length=1
    )
    commentaire_input = discord.ui.TextInput(
        label="Votre Commentaire",
        style=discord.TextStyle.long,
        placeholder="Expliquez votre expérience avec ce staff...",
        required=True,
        max_length=500
    )

    async def on_submit(self, interaction: discord.Interaction):
        # 1. Vérification de la note
        try:
            note = int(self.note_input.value)
            if note < 1 or note > 5:
                raise ValueError
        except ValueError:
            await interaction.response.send_message("❌ La note doit être un chiffre entier compris entre 1 et 5.", ephemeral=True)
            return

        # 2. Recherche du membre staff sur le serveur
        nom_recherche = self.staff_input.value.lower()
        member = None
        for m in interaction.guild.members:
            if nom_recherche in m.name.lower() or nom_recherche in (m.nick or "").lower():
                if est_staff(m):
                    member = m
                    break
        
        if not member:
            await interaction.response.send_message("❌ Staff introuvable ou le membre trouvé ne possède pas le rôle staff configuré.", ephemeral=True)
            return

        # 3. Enregistrement des données
        staff_id = str(member.id)
        if staff_id not in avis_data:
            avis_data[staff_id] = {"nom": member.name, "avis": []}

        avis_data[staff_id]["avis"].append({
            "auteur": interaction.user.name,
            "note": note,
            "commentaire": self.commentaire_input.value,
            "date": interaction.created_at.strftime("%d/%m/%Y à %H:%M")
        })
        save_avis(avis_data)

        # Calcul de la nouvelle moyenne du staff
        avis_list = avis_data[staff_id]["avis"]
        moyenne = sum(a["note"] for a in avis_list) / len(avis_list)

        # 4. Envoi de l'embed avec le joli design demandé
        etoiles = "⭐" * note
        embed = discord.Embed(
            title="✅ Avis enregistré",
            color=discord.Color.green()
        )
        embed.description = (
            f"**Staff :** {member.mention}\n"
            f"**Note :** {etoiles}\n"
            f"**Moyenne actuelle :** {moyenne:.1f} / 5\n"
            f"**Commentaire :** *{self.commentaire_input.value}*"
        )
        
        await interaction.response.send_message(embed=embed)


# Vue contenant le bouton permanent "FAIRE UN AVIS"
class PersistentAvisView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="FAIRE UN AVIS", style=discord.ButtonStyle.success, custom_id="btn_faire_avis", emoji="✍️")
    async def faire_avis_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Ouvre le formulaire pop-up au joueur
        await interaction.response.send_modal(AvisModal())


# ─── COMMANDES DU BOT ───

#
