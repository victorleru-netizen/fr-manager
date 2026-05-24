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

# Fichiers de stockage
AVIS_FILE = "avis.json"
CONFIG_FILE = "config.json"

def load_avis():
    if os.path.exists(AVIS_FILE):
        try:
            with open(AVIS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError:
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
            return {}
    return {}

def save_config(config_data):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config_data, f, indent=4, ensure_ascii=False)

avis_data = load_avis()
config_global = load_config()

# Fonctions utilitaires pour gérer le multi-serveur (Public)
def get_server_config(guild_id: str):
    if guild_id not in config_global:
        config_global[guild_id] = {"roles_staff": [], "salon_affichage": None}
    return config_global[guild_id]

def est_staff(member: discord.Member) -> bool:
    srv_cfg = get_server_config(str(member.guild.id))
    return any(role.id in srv_cfg.get("roles_staff", []) for role in member.roles)


# ─── SYNCHRONISATION GLOBALE ───
@bot.event
async def on_ready():
    print(f"Bot connecté en tant que {bot.user}")
    try:
        synced = await bot.tree.sync()
        print(f"🌍 Synchronisation globale réussie : {len(synced)} commandes enregistrées.")
    except Exception as e:
        print(f"❌ Erreur lors de la synchronisation : {e}")


# ─── LE FORMULAIRE D'AVIS À 4 CRITÈRES (MODAL) ───
class DetailAvisModal(discord.ui.Modal):
    def __init__(self, staff_member: discord.Member):
        super().__init__(title=f"Avis : {staff_member.display_name}")
        self.staff_member = staff_member

        self.prof_input = discord.ui.TextInput(
            label="Professionnalisme (Note de 1 à 5)",
            placeholder="Sérieux et respect des procédures",
            required=True,
            min_length=1,
            max_length=1
        )
        self.symp_input = discord.ui.TextInput(
            label="Sympathie & Accueil (Note de 1 à 5)",
            placeholder="Gentillesse et bonne humeur",
            required=True,
            min_length=1,
            max_length=1
        )
        self.rap_input = discord.ui.TextInput(
            label="Rapidité (Note de 1 à 5)",
            placeholder="Prise en charge et efficacité",
            required=True,
            min_length=1,
            max_length=1
        )
        self.ecoute_input = discord.ui.TextInput(
            label="Écoute (Note de 1 à 5)",
            placeholder="Patience et compréhension du problème",
            required=True,
            min_length=1,
            max_length=1
        )
        self.comm_input = discord.ui.TextInput(
            label="Commentaire général",
            style=discord.TextStyle.long,
            placeholder="Exprimez-vous sur votre expérience avec ce staff...",
            required=True,
            max_length=300
        )

        self.add_item(self.prof_input)
        self.add_item(self.symp_input)
        self.add_item(self.rap_input)
        self.add_item(self.ecoute_input)
        self.add_item(self.comm_input)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            n_prof = int(self.prof_input.value)
            n_symp = int(self.symp_input.value)
            n_rap = int(self.rap_input.value)
            n_ecoute = int(self.ecoute_input.value)
            
            if not all(1 <= n <= 5 for n in [n_prof, n_symp, n_rap, n_ecoute]):
                raise ValueError
        except ValueError:
            await interaction.response.send_message("❌ Toutes les notes doivent être des chiffres entiers compris entre 1 et 5.", ephemeral=True)
            return

        note_moyenne_avis = (n_prof + n_symp + n_rap + n_ecoute) / 4

        guild_id = str(interaction.guild.id)
        if guild_id not in avis_data:
            avis_data[guild_id] = {}

        staff_id = str(self.staff_member.id)
        if staff_id not in avis_data[guild_id]:
            avis_data[guild_id][staff_id] = {"nom": self.staff_member.name, "avis": []}

        avis_data[guild_id][staff_id]["avis"].append({
            "auteur": interaction.user.name,
            "note": note_moyenne_avis,
            "n_prof": n_prof,
            "n_symp": n_symp,
            "n_rap": n_rap,
            "n_ecoute": n_ecoute,
            "commentaire": self.comm_input.value,
            "date": interaction.created_at.strftime("%d/%m/%Y à %H:%M")
        })
        save_avis(avis_data)

        avis_list = avis_data[guild_id][staff_id]["avis"]
        moyenne_generale = sum(a["note"] for a in avis_list) / len(avis_list)

        e_prof = "⭐" * n_prof
        e_symp = "⭐" * n_symp
        e_rap = "⭐" * n_rap
        e_ecoute = "⭐" * n_ecoute
        e_globale = "⭐" * int(round(note_moyenne_avis))
        
        embed = discord.Embed(
            title="✅ Nouvel Avis Staff Enregistré",
            color=discord.Color.green()
        )
        embed.description = (
            f"**Staff évalué :** {self.staff_member.mention}\n\n"
            f"**⭐ NOTE GLOBALE DE L'AVIS : {e_globale} ({note_moyenne_avis:.1f}/5)**\n"
            f"▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬\n"
            f"**📊 Détails des critères :**\n"
            f"💼 Professionnalisme : {e_prof} ({n_prof}/5)\n"
            f"❤️ Sympathie & Accueil : {e_symp} ({n_symp}/5)\n"
            f"⚡ Rapidité : {e_rap} ({n_rap}/5)\n"
            f"👂 Écoute & Patience : {e_ecoute} ({n_ecoute}/5)\n\n"
            f"📈 **Moyenne générale historique du staff :** {moyenne_generale:.1f} / 5\n\n"
            f"**Commentaire :** *{self.comm_input.value}*\n"
            f"*Soumis par : {interaction.user.mention}*"
        )
        
        srv_cfg = get_server_config(guild_id)
        salon_id = srv_cfg.get("salon_affichage")
        salon_cible = interaction.guild.get_channel(salon_id) if salon_id else None
        
        if salon_cible:
            try:
                await salon_cible.send(embed=embed)
                await interaction.response.send_message(f"❤️ Merci ! Votre avis a été publié dans {salon_cible.mention}.", ephemeral=True)
            except Exception:
                await interaction.response.send_message(embed=embed)
        else:
            await interaction.response.send_message(embed=embed)


# ─── SÉLECTION DU STAFF (MENU DÉROULANT) ───
class StaffSelect(discord.ui.Select):
    def __init__(self, membres_staff):
        options = [
            discord.SelectOption(label=m.display_name, value=str(m.id), description=f"Noter {m.display_name}")
            for m in membres_staff[:25]
        ]
        super().__init__(placeholder="Sélectionnez le membre du staff à évaluer...", options=options)

    async def callback(self, interaction: discord.Interaction):
        staff_id = int(self.values[0])
        staff_member = interaction.guild.get_member(staff_id)
        
        if not staff_member:
            await interaction.response.send_message("❌ Ce membre du staff ne fait plus partie du serveur.", ephemeral=True)
            return

        await interaction.response.send_modal(DetailAvisModal(staff_member))


class DropdownStaffView(discord.ui.View):
    def __init__(self, membres_staff):
        super().__init__(timeout=60)
        self.add_item(StaffSelect(membres_staff))


class PersistentAvisView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="FAIRE UN AVIS", style=discord.ButtonStyle.success, custom_id="btn_faire_avis", emoji="✍️")
    async def faire_avis_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        membres_staff = [m for m in interaction.guild.members if est_staff(m)]

        if not membres_staff:
            await interaction.response.send_message("❌ Aucun membre de l'équipe n'est disponible ou configuré pour le moment.", ephemeral=True)
            return

        view = DropdownStaffView(membres_staff)
        await interaction.response.send_message("👇 Choisissez le membre du staff que vous souhaitez évaluer :", view=view, ephemeral=True)


# ─── 🛠️ CONFIGURATION DES RÔLES ET SALONS (SÉCURISÉ MULTI-SERVEUR) ───

class ChannelSelectComponent(discord.ui.ChannelSelect):
    def __init__(self):
        super().__init__(
            placeholder="Étape 2 : Choisissez le salon de publication...",
            channel_types=[discord.ChannelType.text]
        )

    async def callback(self, interaction: discord.Interaction):
        guild_id = str(interaction.guild.id)
        salon_choisi = self.values[0] # Récupère l'objet channel directement
        
        srv_cfg = get_server_config(guild_id)
        srv_cfg["salon_affichage"] = salon_choisi.id
        save_config(config_global)
        
        roles_mentions = [interaction.guild.get_role(r_id).mention for r_id in srv_cfg["roles_staff"] if interaction.guild.get_role(r_id)]

        embed = discord.Embed(
            title="⚙️ Configuration Terminée avec Succès !",
            description=(
                f"✅ **Rôles Staff :** {', '.join(roles_mentions) if roles_mentions else 'Aucun'}\n"
                f"✅ **Salon de publication :** {salon_choisi.mention}\n\n"
                f"Le bot est prêt. Lancez la commande `/avis-view` dans le salon où vous voulez mettre le bouton d'avis."
            ),
            color=discord.Color.green()
        )
        await interaction.response.edit_message(embed=embed, view=None)


class ConfigChannelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=300)
        self.add_item(ChannelSelectComponent())


class RoleSelectComponent(discord.ui.Select):
    def __init__(self, guild: discord.Guild):
        options = [discord.SelectOption(label=role.name, value=str(role.id)) for role in guild.roles if role.name != "@everyone"][:25]
        super().__init__(placeholder="Étape 1 : Sélectionnez le ou les rôles staff...", min_values=1, max_values=len(options), options=options)

    async def callback(self, interaction: discord.Interaction):
        guild_id = str(interaction.guild.id)
        selected_roles = [int(r_id) for r_id in self.values]
        
        srv_cfg = get_server_config(guild_id)
        srv_cfg["roles_staff"] = selected_roles
        save_config(config_global)

        embed = discord.Embed(
            title="⚙️ Étape 2 : Salon d'affichage",
            description="Les rôles ont été enregistrés ! Maintenant, choisissez le salon textuel dans lequel le bot doit publier les avis reçus.",
            color=discord.Color.orange()
        )
        view = ConfigChannelView()
        await interaction.response.edit_message(embed=embed, view=view)


class ConfigRolesView(discord.ui.View):
    def __init__(self, guild: discord.Guild):
        super().__init__(timeout=300)
        self.add_item(RoleSelectComponent(guild))


class InitialConfigView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Démarrer la configuration", style=discord.ButtonStyle.primary, custom_id="config_start_btn")
    async def config_start_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="⚙️ Étape 1 : Rôles du Staff",
            description="Sélectionnez dans la liste ci-dessous les rôles qui définissent les membres de votre équipe.",
            color=discord.Color.orange()
        )
        view = ConfigRolesView(interaction.guild)
        await interaction.response.edit_message(embed=embed, view=view)


# ─── COMMANDES DU BOT ───

@bot.tree.command(name="avis-view", description="Afficher le bouton permanent pour laisser un avis")
async def avis_view(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("Seuls les administrateurs peuvent utiliser cette commande.", ephemeral=True)
        return

    embed = discord.Embed(
        title="📋 Évaluation de l'Équipe Staff",
        description=(
            "Votre avis nous intéresse ! Que ce soit suite à un ticket, une aide ou une interaction, "
            "aidez-nous à améliorer la qualité de notre service.\n\n"
            "Cliquez sur le bouton ci-dessous, choisissez votre staff et notez-le sur nos 4 critères de qualité."
        ),
        color=discord.Color.blue()
    )
    
    await interaction.channel.send(embed=embed, view=PersistentAvisView())
    await interaction.response.send_message("✅ Le système d'avis par critères a été installé dans ce salon !", ephemeral=True)


@bot.tree.command(name="avis-config", description="Configurer les rôles et le salon d'affichage des avis")
async def avis_config(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("Seuls les administrateurs peuvent configurer le bot.", ephemeral=True)
        return

    embed = discord.Embed(
        title="⚙️ Configuration du Système d'Avis",
        description="Cliquez sur le bouton ci-dessous pour configurer pas-à-pas les rôles de votre staff et le salon de réception des avis.",
        color=discord.Color.blue()
    )

    await interaction.response.send_message(embed=embed, view=InitialConfigView(), ephemeral=True)


async def staff_autocomplete(interaction: discord.Interaction, current: str):
    guild = interaction.guild
    if not guild:
        return []
    guild_id = str(guild.id)
    srv_cfg = get_server_config(guild_id)
    
    choix = []
    for member in guild.members:
        if any(role.id in srv_cfg.get("roles_staff", []) for role in member.roles):
            if current.lower() in member.name.lower() or current.lower() in (member.nick or "").lower():
                choix.append(app_commands.Choice(name=member.display_name, value=str(member.id)))
    return choix[:25]


@bot.tree.command(name="voir_avis", description="Voir les avis d'un membre du staff")
@app_commands.autocomplete(staff=staff_autocomplete)
async def voir_avis(interaction: discord.Interaction, staff: str):
    try:
        member = interaction.guild.get_member(int(staff))
        if not member:
            member = await interaction.guild.fetch_member(int(staff))
    except Exception:
        await interaction.response.send_message("❌ Membre introuvable.", ephemeral=True)
        return

    guild_id = str(interaction.guild.id)
    if guild_id not in avis_data or str(member.id) not in avis_data[guild_id] or not avis_data[guild_id][str(member.id)]["avis"]:
        embed = discord.Embed(title="❌ Aucun avis trouvé", description=f"Aucun avis n'a été enregistré pour **{member.display_name}**.", color=discord.Color.red())
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    avis_list = avis_data[guild_id][str(member.id)]["avis"]
    moyenne = sum(a["note"] for a in avis_list) / len(avis_list)

    embed = discord.Embed(title=f"📋 Profil de {member.display_name}", color=discord.Color.blue())
    embed.description = f"**Staff :** {member.mention}\n**Moyenne globale historique :** {moyenne:.1f} / 5\n\n─── **Derniers avis reçus** ───"

    for avis_item in avis_list:
        etoiles = "⭐" * int(round(avis_item['note']))
        embed.add_field(
            name=f"Par {avis_item['auteur']} (le {avis_item['date']})",
            value=f"**Note moyenne :** {etoiles} ({avis_item['note']:.1f}/5)\n**Commentaire :** *{avis_item['commentaire']}*",
            inline=False
        )
    await interaction.response.send_message(embed=embed)

TOKEN = os.getenv("DISCORD_TOKEN")
bot.run(TOKEN)
