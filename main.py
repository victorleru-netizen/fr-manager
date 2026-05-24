import discord
from discord.ext import commands
import json
import os
from dotenv import load_dotenv
from flask import Flask
import threading
from discord import app_commands
from datetime import datetime, timedelta

# Charger les variables d'environnement
load_dotenv()

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix="/", intents=intents)

app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is alive!"

def run_flask():
    app.run(host='0.0.0.0', port=8080)

flask_thread = threading.Thread(target=run_flask)
flask_thread.start()

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

def get_server_config(guild_id: str):
    if guild_id not in config_global:
        config_global[guild_id] = {"roles_staff": [], "salon_affichage": None, "blacklist": []}
    if "blacklist" not in config_global[guild_id]:
        config_global[guild_id]["blacklist"] = []
    return config_global[guild_id]

def est_staff(member: discord.Member) -> bool:
    srv_cfg = get_server_config(str(member.guild.id))
    return any(role.id in srv_cfg.get("roles_staff", []) for role in member.roles)

def est_blacklist(member: discord.Member) -> bool:
    srv_cfg = get_server_config(str(member.guild.id))
    return str(member.id) in srv_cfg.get("blacklist", [])


@bot.event
async def on_ready():
    print(f"Bot connecté en tant que {bot.user}")
    try:
        synced = await bot.tree.sync()
        print(f"🌍 Synchronisation globale réussie : {len(synced)} commandes.")
    except Exception as e:
        print(f"❌ Erreur synchronisation : {e}")


# ─── FORMULAIRE PRINCIPAL CORRIGÉ (5 CHAMPS PILE) ───
class DetailAvisModal(discord.ui.Modal):
    def __init__(self, staff_member: discord.Member):
        super().__init__(title=f"Avis : {staff_member.display_name}")
        self.staff_member = staff_member

        self.prof_input = discord.ui.TextInput(label="Professionnalisme (Note de 1 à 5)", placeholder="Sérieux...", required=True, min_length=1, max_length=1)
        self.symp_input = discord.ui.TextInput(label="Sympathie & Accueil (Note de 1 à 5)", placeholder="Gentillesse...", required=True, min_length=1, max_length=1)
        self.rap_input = discord.ui.TextInput(label="Rapidité (Note de 1 à 5)", placeholder="Efficacité...", required=True, min_length=1, max_length=1)
        self.ecoute_input = discord.ui.TextInput(label="Écoute (Note de 1 à 5)", placeholder="Patience...", required=True, min_length=1, max_length=1)
        self.anonyme_input = discord.ui.TextInput(label="Rester anonyme ? (Oui / Non)", placeholder="Écrivez Oui ou Non", required=True, min_length=2, max_length=3, default="Non")

        self.add_item(self.prof_input)
        self.add_item(self.symp_input)
        self.add_item(self.rap_input)
        self.add_item(self.ecoute_input)
        self.add_item(self.anonyme_input)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            n_prof = int(self.prof_input.value)
            n_symp = int(self.symp_input.value)
            n_rap = int(self.rap_input.value)
            n_ecoute = int(self.ecoute_input.value)
            
            if not all(1 <= n <= 5 for n in [n_prof, n_symp, n_rap, n_ecoute]):
                raise ValueError
        except ValueError:
            await interaction.response.send_message("❌ Toutes les notes doivent être des chiffres entiers entre 1 et 5.", ephemeral=True)
            return

        est_anonyme = self.anonyme_input.value.strip().lower() in ["oui", "ouis", "y", "yes"]

        # Pour contourner le bug, on demande le commentaire via le chat de manière interactive
        await interaction.response.send_message(
            f"📥 **Notes enregistrées !** Veuillez maintenant taper votre **commentaire général** directement dans le chat ci-dessous pour finaliser l'avis sur {self.staff_member.mention}.", 
            ephemeral=True
        )

        def check(m):
            return m.author.id == interaction.user.id and m.channel.id == interaction.channel.id

        try:
            # On attend le texte du joueur pendant 5 minutes maximum
            msg = await bot.wait_for('message', check=check, timeout=300.0)
            commentaire_texte = msg.content
            
            # On essaie de supprimer le message du joueur pour garder le salon propre (si le bot a les perms)
            try:
                await msg.delete()
            except Exception:
                pass
                
        except threading.TimeoutError:
            await interaction.followup.send("⏳ Temps écoulé. L'avis a été annulé, veuillez recommencer.", ephemeral=True)
            return

        # Traitement et sauvegarde des données
        note_moyenne_avis = (n_prof + n_symp + n_rap + n_ecoute) / 4
        maintenant_str = interaction.created_at.strftime("%d/%m/%Y %H:%M:%S")
        guild_id = str(interaction.guild.id)
        
        if guild_id not in avis_data:
            avis_data[guild_id] = {}
        staff_id = str(self.staff_member.id)
        if staff_id not in avis_data[guild_id]:
            avis_data[guild_id][staff_id] = {"nom": self.staff_member.name, "avis": []}

        avis_data[guild_id][staff_id]["avis"].append({
            "auteur_id": str(interaction.user.id),
            "auteur_nom": interaction.user.name,
            "note": note_moyenne_avis,
            "n_prof": n_prof,
            "n_symp": n_symp,
            "n_rap": n_rap,
            "n_ecoute": n_ecoute,
            "commentaire": commentaire_texte,
            "anonyme": est_anonyme,
            "date": maintenant_str
        })
        save_avis(avis_data)

        avis_list = avis_data[guild_id][staff_id]["avis"]
        moyenne_generale = sum(a["note"] for a in avis_list) / len(avis_list)

        embed = discord.Embed(title="✅ Nouvel Avis Staff Enregistré", color=discord.Color.green())
        affichage_auteur = "👤 Membre Anonyme" if est_anonyme else interaction.user.mention
        
        embed.description = (
            f"**Staff évalué :** {self.staff_member.mention}\n\n"
            f"**⭐ NOTE GLOBALE DE L'AVIS : {'⭐' * int(round(note_moyenne_avis))} ({note_moyenne_avis:.1f}/5)**\n"
            f"▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬\n"
            f"**📊 Détails des critères :**\n"
            f"💼 Professionnalisme : {'⭐' * n_prof} ({n_prof}/5)\n"
            f"❤️ Sympathie & Accueil : {'⭐' * n_symp} ({n_symp}/5)\n"
            f"⚡ Rapidité : {'⭐' * n_rap} ({n_rap}/5)\n"
            f"👂 Écoute & Patience : {'⭐' * n_ecoute} ({n_ecoute}/5)\n\n"
            f"📈 **Moyenne générale historique du staff :** {moyenne_generale:.1f} / 5\n\n"
            f"**Commentaire :** *{commentaire_texte}*\n"
            f"*Soumis par : {affichage_auteur}*"
        )
        
        srv_cfg = get_server_config(guild_id)
        salon_cible = interaction.guild.get_channel(srv_cfg.get("salon_affichage"))
        
        if salon_cible:
            await salon_cible.send(embed=embed)
            await interaction.followup.send(f"❤️ Merci ! Votre avis a été envoyé dans {salon_cible.mention}.", ephemeral=True)
        else:
            await interaction.followup.send(embed=embed, ephemeral=True)


# ─── TOUTES LES COMMANDES ET COMPOSANTS RESTANTS (SÉCURISÉS) ───
class StaffSelect(discord.ui.Select):
    def __init__(self, membres_staff):
        options = [discord.SelectOption(label=m.display_name, value=str(m.id), description=f"Noter {m.display_name}") for m in membres_staff[:25]]
        super().__init__(placeholder="Sélectionnez le membre du staff à évaluer...", options=options)

    async def callback(self, interaction: discord.Interaction):
        if est_blacklist(interaction.user):
            await interaction.response.send_message("❌ Vous avez été banni du système d'avis.", ephemeral=True)
            return

        staff_id = self.values[0]
        guild_id = str(interaction.guild.id)
        
        staff_member = interaction.guild.get_member(int(staff_id))
        if not staff_member:
            await interaction.response.send_message("❌ Ce membre du staff ne fait plus partie du serveur.", ephemeral=True)
            return

        if guild_id in avis_data and staff_id in avis_data[guild_id]:
            avis_joueur = [a for a in avis_data[guild_id][staff_id]["avis"] if a.get("auteur_id") == str(interaction.user.id)]
            if avis_joueur:
                dernier_avis = avis_joueur[-1]
                try:
                    date_dernier_avis = datetime.strptime(dernier_avis["date"], "%d/%m/%Y %H:%M:%S")
                except ValueError:
                    date_dernier_avis = datetime.strptime(dernier_avis["date"], "%d/%m/%Y à %H:%M")

                if datetime.utcnow() - date_dernier_avis < timedelta(hours=24):
                    temps_restant = timedelta(hours=24) - (datetime.utcnow() - date_dernier_avis)
                    heures, reste = divmod(temps_restant.seconds, 3600)
                    minutes, _ = divmod(reste, 60)
                    await interaction.response.send_message(f"⏳ **Limite de temps :** Veuillez attendre encore **{heures}h et {minutes}min** avant de renoter ce staff.", ephemeral=True)
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
        if est_blacklist(interaction.user):
            await interaction.response.send_message("❌ Vous avez été banni du système d'avis.", ephemeral=True)
            return

        membres_staff = [m for m in interaction.guild.members if est_staff(m)]
        if not membres_staff:
            await interaction.response.send_message("❌ Aucun membre du staff n'est configuré ou disponible.", ephemeral=True)
            return

        await interaction.response.send_message("👇 Choisissez le membre du staff que vous souhaitez évaluer :", view=DropdownStaffView(membres_staff), ephemeral=True)


class ChannelSelectComponent(discord.ui.ChannelSelect):
    def __init__(self):
        super().__init__(placeholder="Étape 2 : Choisissez le salon de publication...", channel_types=[discord.ChannelType.text])

    async def callback(self, interaction: discord.Interaction):
        guild_id = str(interaction.guild.id)
        salon_choisi = self.values[0]
        srv_cfg = get_server_config(guild_id)
        srv_cfg["salon_affichage"] = salon_choisi.id
        save_config(config_global)
        
        roles_mentions = [interaction.guild.get_role(r_id).mention for r_id in srv_cfg["roles_staff"] if interaction.guild.get_role(r_id)]
        embed = discord.Embed(title="⚙️ Configuration Réussie !", description=f"✅ **Rôles Staff :** {', '.join(roles_mentions)}\n✅ **Salon :** {salon_choisi.mention}\n\nLancez `/avis-view` pour l'activer.", color=discord.Color.green())
        await interaction.response.edit_message(embed=embed, view=None)


class ConfigChannelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=300)
        self.add_item(ChannelSelectComponent())


class RoleSelectComponent(discord.ui.Select):
    def __init__(self, guild: discord.Guild):
        options = [discord.SelectOption(label=role.name, value=str(role.id)) for role in guild.roles if role.name != "@everyone"][:25]
        super().__init__(placeholder="Étape 1 : Sélectionnez les rôles staff...", min_values=1, max_values=len(options), options=options)

    async def callback(self, interaction: discord.Interaction):
        guild_id = str(interaction.guild.id)
        srv_cfg = get_server_config(guild_id)
        srv_cfg["roles_staff"] = [int(r_id) for r_id in self.values]
        save_config(config_global)

        embed = discord.Embed(title="⚙️ Étape 2 : Salon d'affichage", description="Rôles enregistrés ! Choisissez maintenant le salon de réception.", color=discord.Color.orange())
        await interaction.response.edit_message(embed=embed, view=ConfigChannelView())


class ConfigRolesView(discord.ui.View):
    def __init__(self, guild: discord.Guild):
        super().__init__(timeout=300)
        self.add_item(RoleSelectComponent(guild))


class InitialConfigView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Démarrer la configuration", style=discord.ButtonStyle.primary, custom_id="config_start_btn")
    async def config_start_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(title="⚙️ Étape 1 : Rôles du Staff", description="Sélectionnez les rôles définissant votre staff.", color=discord.Color.orange())
        await interaction.response.edit_message(embed=embed, view=ConfigRolesView(interaction.guild))


@bot.tree.command(name="mon-profil", description="Voir mes propres statistiques d'avis (Réservé au staff)")
async def mon_profil(interaction: discord.Interaction):
    if not est_staff(interaction.user):
        await interaction.response.send_message("❌ Réservé aux membres du staff.", ephemeral=True)
        return

    guild_id = str(interaction.guild.id)
    staff_id = str(interaction.user.id)

    if guild_id not in avis_data or staff_id not in avis_data[guild_id] or not avis_data[guild_id][staff_id]["avis"]:
        await interaction.response.send_message("📊 Vous n'avez pas encore reçu d'avis.", ephemeral=True)
        return

    avis_list = avis_data[guild_id][staff_id]["avis"]
    total = len(avis_list)
    
    m_globale = sum(a["note"] for a in avis_list) / total
    embed = discord.Embed(title=f"📊 Votre Profil Staff - {interaction.user.display_name}", color=discord.Color.teal())
    embed.description = f"**Moyenne globale :** {'⭐' * int(round(m_globale))} ({m_globale:.2f}/5)\n**Nombre total d'avis :** 💬 {total}"
    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="top-staff", description="Afficher le TOP 3 des staffs les mieux notés")
async def top_staff(interaction: discord.Interaction):
    guild_id = str(interaction.guild.id)
    if guild_id not in avis_data or not avis_data[guild_id]:
        await interaction.response.send_message("❌ Aucun avis enregistré.", ephemeral=True)
        return

    scores = []
    for s_id, s_data in avis_data[guild_id].items():
        if s_data["avis"]:
            moy = sum(a["note"] for a in s_data["avis"]) / len(s_data["avis"])
            scores.append((s_id, s_data["nom"], moy, len(s_data["avis"])))

    scores.sort(key=lambda x: (x[2], x[3]), reverse=True)
    top_3 = scores[:3]

    embed = discord.Embed(title="🏆 TOP 3 - Équipe Staff", color=discord.Color.gold())
    medailles = ["🥇", "🥈", "🥉"]
    desc = ""
    for i, (s_id, nom, moy, count) in enumerate(top_3):
        desc += f"{medailles[i]} **{nom}** (<@{s_id}>)\n┗ Score : **{moy:.1f}/5** ({count} avis)\n\n"
    embed.description = desc
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="avis-stats", description="Voir le classement de l'équipe (Admin)")
async def avis_stats(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("Seuls les admins peuvent faire cela.", ephemeral=True)
        return

    guild_id = str(interaction.guild.id)
    if guild_id not in avis_data or not avis_data[guild_id]:
        await interaction.response.send_message("❌ Aucune donnée.", ephemeral=True)
        return

    scores = [(s_data["nom"], sum(a["note"] for a in s_data["avis"]) / len(s_data["avis"]), len(s_data["avis"])) for s_id, s_data in avis_data[guild_id].items() if s_data["avis"]]
    scores.sort(key=lambda x: x[1], reverse=True)

    embed = discord.Embed(title="📊 Classement Interne", color=discord.Color.purple())
    embed.description = "\n".join([f"**#{idx} {nom}** — **{moy:.2f}/5** ({count} avis)" for idx, (nom, moy, count) in enumerate(scores, start=1)])
    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="avis-blacklist", description="Bloquer ou débloquer un membre (Admin)")
@app_commands.choices(action=[app_commands.Choice(name="Bloquer", value="add"), app_commands.Choice(name="Débloquer", value="remove")])
async def avis_blacklist(interaction: discord.Interaction, action: str, membre: discord.Member):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("Permissions insuffisantes.", ephemeral=True)
        return

    guild_id = str(interaction.guild.id)
    srv_cfg = get_server_config(guild_id)
    m_id = str(membre.id)

    if action == "add" and m_id not in srv_cfg["blacklist"]:
        srv_cfg["blacklist"].append(m_id)
        save_config(config_global)
        await interaction.response.send_message(f"✅ {membre.mention} banni du système.", ephemeral=True)
    elif action == "remove" and m_id in srv_cfg["blacklist"]:
        srv_cfg["blacklist"].remove(m_id)
        save_config(config_global)
        await interaction.response.send_message(f"✅ {membre.mention} débanni.", ephemeral=True)
    else:
        await interaction.response.send_message("Statut inchangé.", ephemeral=True)


@bot.tree.command(name="avis-clear", description="Effacer les avis d'un staff ou du serveur (Admin)")
async def avis_clear(interaction: discord.Interaction, staff: discord.Member = None):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("Permissions insuffisantes.", ephemeral=True)
        return

    guild_id = str(interaction.guild.id)
    if staff and guild_id in avis_data and str(staff.id) in avis_data[guild_id]:
        del avis_data[guild_id][str(staff.id)]
        save_avis(avis_data)
        await interaction.response.send_message(f"🗑️ Avis effacés pour {staff.display_name}.", ephemeral=True)
    elif not staff:
        avis_data[guild_id] = {}
        save_avis(avis_data)
        await interaction.response.send_message("🗑️ Tout le serveur a été réinitialisé.", ephemeral=True)
    else:
        await interaction.response.send_message("Aucune modification effectuée.", ephemeral=True)


@bot.tree.command(name="avis-view", description="Afficher le bouton pour laisser un avis")
async def avis_view(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("Permissions insuffisantes.", ephemeral=True)
        return
    embed = discord.Embed(title="📋 Évaluation de l'Équipe Staff", description="Cliquez ci-dessous pour noter un membre de l'équipe.", color=discord.Color.blue())
    await interaction.channel.send(embed=embed, view=PersistentAvisView())
    await interaction.response.send_message("✅ Système déployé !", ephemeral=True)


@bot.tree.command(name="avis-config", description="Configuration globale")
async def avis_config(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("Permissions insuffisantes.", ephemeral=True)
        return
    await interaction.response.send_message(embed=discord.Embed(title="⚙️ Configuration", description="Démarrez l'assistant.", color=discord.Color.blue()), view=InitialConfigView(), ephemeral=True)


@bot.tree.command(name="voir_avis", description="Voir les avis d'un staff")
@app_commands.autocomplete(staff=staff_autocomplete)
async def voir_avis(interaction: discord.Interaction, staff: str):
    guild_id = str(interaction.guild.id)
    if guild_id not in avis_data or staff not in avis_data[guild_id] or not avis_data[guild_id][staff]["avis"]:
        await interaction.response.send_message("❌ Aucun avis.", ephemeral=True)
        return

    avis_list = avis_data[guild_id][staff]["avis"]
    moyenne = sum(a["note"] for a in avis_list) / len(avis_list)

    embed = discord.Embed(title=f"📋 Profil de {avis_data[guild_id][staff]['nom']}", color=discord.Color.blue())
    embed.description = f"**Moyenne :** {moyenne:.1f} / 5\n\n─── **Derniers avis** ───"

    for avis_item in avis_list:
        nom_auteur = " Anonyme" if avis_item.get("anonyme") else avis_item.get("auteur_nom", "Anonyme")
        embed.add_field(name=f"Par {nom_auteur} (le {avis_item['date']})", value=f"Note : {'⭐' * int(round(avis_item['note']))}\nCommentaire : *{avis_item['commentaire']}*", inline=False)
    await interaction.response.send_message(embed=embed)

TOKEN = os.getenv("DISCORD_TOKEN")
bot.run(TOKEN)
    
