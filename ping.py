import csv # Módulo csv
import os # Módulos com funções do SO
import sys # Este módulo fornece acesso a algumas variáveis ​​usadas ou mantidas pelo interpretador.
import socket # Módulo de implementação para operações de soquete.
import struct # Funções para converter entre valores Python e estruturas C
import select # Este módulo suporta E / S assíncronos
import time # Este módulo fornece várias funções relacionadas ao tempo

if sys.platform == "win32":     # Identificador do SO 
    default_timer = time.clock  # No Windows, o melhor timer é o time.clock ()
else:
    default_timer = time.time   # Na maioria das outras plataformas, o melhor timer é o time.time ()

lista = []
NUM_PACKETS = 4    # números de pacotes
PACKET_SIZE = 64   # Tamanho de pacotes
WAIT_TIMEOUT = 3.0  # tempo de espera para timeout
ICMP_ECHO = 8  # Echo de requisição
ICMP_MAX_RECV = 2048  # Tamanho máximo do buffer de entrada
MAX_SLEEP = 1000 # Máximo tempo de espera


class MyStats:
    thisIP = "0.0.0.0"          # Máscara do IP
    pktsSent = 0                # pacotes enviados
    pktsRcvd = 0                # pacotes recebidos
    minTime = 999999999         # tempo mínimo
    maxTime = 0                 # tempo máximo
    totTime = 0                 # tempo total
    avrgTime = 0                # tempo médio
    fracLoss = 1.0              # pacotes que fracassaram


myStats = MyStats  # atribuindo a Class MyStats a um Objeto myStats

#=============================================================================#


def checksum(source_string): # verificar a integridade de dados transmitidos
    """
    Verifica a integridade de dados transmitidos através e retorna um valor númerico
    que se refere a ordem do dado e seu conteúdo, na hora da sua transmissão
    """
    countTo = (int(len(source_string)/2))*2 # tamanho do bytes de dados
    soma = 0   
    count = 0  

    menosByte = 0 
    maisByte = 0  
    while count < countTo:
        """Um indicador da ordem de bytes nativa. Isso terá o valor 
        'big' em plataformas big-endian (primeiro byte mais significativo) e 
        'little' em plataformas little-endian (menos significativo primeiro byte)."""
        if (sys.byteorder == "little"):
            menosByte = source_string[count]     
            maisByte = source_string[count + 1] # bit mais significativo
        else:
            menosByte = source_string[count + 1] # bit menos significativo
            maisByte = source_string[count]     
    
        soma = soma + (maisByte * 256 + menosByte)
        count += 2

    if countTo < len(source_string):  # Verifica tamanho do bytes de dados impar
        menosByte = source_string[len(source_string)-1] # bit menos significativo
        soma += menosByte 

    soma &= 0xffffffff

    soma = (soma >> 16) + (soma & 0xffff)    
    soma += (soma >> 16)                  
    res = ~soma & 0xffff               
    res = socket.htons(res)

    return res

#=============================================================================#


def atraso(myStats, destIP, hostname, timeout, mySeqNumber, packet_size, quiet=False):
    """
    Retorna o atraso (em ms) ou Nenhum no tempo limite.
    """
    delay = None

    """
    socket.AF_INET, é uma string que representa um nome de host na notação de domínio da Internet 
    como 'daring.cwi.nl' ou um endereço IPv4 como '100.50.200.5' e porta é um inteiro."""
    """
    socket.getprotobyname(protocolname), Traduz um nome de protocolo da Internet (por exemplo, 'icmp') 
    para uma constante adequada para passar como o terceiro argumento (opcional) 
    para a função socket (). Isso geralmente é necessário apenas para soquetes abertos 
    no modo "bruto" (SOCK_RAW); para os modos normais de soquete, o protocolo correto é 
    escolhido automaticamente se o protocolo for omitido ou zero.
    """

    try: 
        mySocket = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.getprotobyname("icmp"))
    except socket.error as e:
        print("Falhou!!!. (Erro de socket: '%s')" % e.args[1])

    my_ID = os.getpid() & 0xFFFF # retorna a identificação do processo atual.

    sentTime = send_one_ping(mySocket, destIP, my_ID, mySeqNumber, packet_size) # retorna o tempo enviado
    if sentTime == None:
        mySocket.close()
        return delay

    myStats.pktsSent += 1 # contador de pacotes enviados

    # retorna o tempo de resposta, o tamanho dado, o ping pingado, o numero de seq, id e timeout 
    recvTime, dataSize, iphSrcIP, icmpSeqNumber, iphTTL = receive_one_ping(
        mySocket, my_ID, timeout) 
    mySocket.close()

    if recvTime: # tempo de resposta for verdadeiro
        delay = (recvTime-sentTime)*1000 # tempo de resposta - tempo de envio = delay(ms)
        if not quiet:
            # exibição das respostas do ping
            print("Resposta com %d bytes de %s: icmp_seq=%d ttl=%d time=%d ms" % (
                dataSize, socket.inet_ntoa(struct.pack("!I", iphSrcIP)), icmpSeqNumber, iphTTL, delay)
            )
        myStats.pktsRcvd += 1 # contador de pacotes recebidos
        myStats.totTime += delay # contador do tempo total (todos os times desse host) 
        if myStats.minTime > delay:
            myStats.minTime = delay # contador tempo mínimo
        if myStats.maxTime < delay: 
            myStats.maxTime = delay # contador tempo máximo
    else:
        delay = None
        print("Requesição excedeu o tempo limite.")

    return delay

#=============================================================================#


def send_one_ping(mySocket, destIP, myID, mySeqNumber, packet_size):
    """
    Envia um ping para o> destIP <fornecido
    """
   
    myChecksum = 0 # contador da soma de verificação

    # Faça um cabeçalho fictício com uma soma de verificação 0
    # Retorne uma string contendo os valores compactados de acordo com o formato especificado. 
    header = struct.pack(
        "!BBHHH", ICMP_ECHO, 0, myChecksum, myID, mySeqNumber
    )

    padBytes = []
    startVal = 0x42
 
    for i in range(startVal, startVal + (packet_size-8)):
            padBytes += [(i & 0xff)]  # Mantenha os caracteres no intervalo de 0 a 255
    data = bytearray(padBytes)

    # Calculo a soma de verificação nos dados e no cabeçalho fictício.
    myChecksum = checksum(header + data)  # A soma de verificação está em ordem de rede

    # Agora que temos a soma de verificação correta, colocamos isso. 
    # É apenas mais fácil, para criar um novo cabeçalho do que colocá-lo no modelo.
    header = struct.pack(
        "!BBHHH", ICMP_ECHO, 0, myChecksum, myID, mySeqNumber
    )

    # pacotes com a integridade dos dados verificada e com cabeçalho checksum adicionado.
    packet = header + data

    sendTime = default_timer() # Essa função retorna o tempo de espera junto com o tempo da CPU e depende da plataforma. 

    try:
        """ 
        socket.sendto(bytes, address)
        Retornar o número de bytes enviados.
        """
        mySocket.sendto(packet, (destIP, 1))
    except socket.error as e:
        print("Falha Geral (%s)" % (e.args[1]))
        return

    return sendTime

#=============================================================================#


def receive_one_ping(mySocket, myID, timeout):
    """
    Recebe o ping do soquete. Tempo limite = em ms
    """
    timeLeft = timeout/1000

    while True:  # Loop enquanto aguarda o pacote ou o timeout 
        startedSelect = default_timer() # Essa função retorna o tempo de espera junto com o tempo da CPU e depende da plataforma. 

        whatReady = select.select([mySocket], [], [], timeLeft)
        howLongInSelect = (default_timer() - startedSelect)
        if whatReady[0] == []:  # timeout
            return None, 0, 0, 0, 0

        timeReceived = default_timer() # Essa função retorna o tempo de espera junto com o tempo da CPU e depende da plataforma. 

        """
        Receba dados do soquete. O valor de retorno é um par (bytes, endereço) em que bytes é um objeto de bytes que representa
        os dados recebidos e endereço é o endereço do soquete que envia os dados 
        """
        recPacket, addr = mySocket.recvfrom(ICMP_MAX_RECV) 

        """
        struct.unpack( fmt , string ) 
        Descompacte a sequência (presumivelmente empacotada por ) de acordo com o formato fornecido. 
        O resultado é uma tupla, mesmo que contenha exatamente um item.
        """
        ipHeader = recPacket[:20]
        iphVersion, iphTypeOfSvc, iphLength, \
            iphID, iphFlags, iphTTL, iphProtocol, \
            iphChecksum, iphSrcIP, iphDestIP = struct.unpack(
                "!BBHHHBBHII", ipHeader
            )

        icmpHeader = recPacket[20:28]
        icmpType, icmpCode, icmpChecksum, \
            icmpPacketID, icmpSeqNumber = struct.unpack(
                "!BBHHH", icmpHeader
            )

        if icmpPacketID == myID:
            dataSize = len(recPacket) - 28
            # retorna o tempo de resposta, o tamanho dado, o ping pingado, o numero de seq, id e timeout  
            return timeReceived, (dataSize+8), iphSrcIP, icmpSeqNumber, iphTTL

        timeLeft = timeLeft - howLongInSelect
        if timeLeft <= 0:
            return None, 0, 0, 0, 0 # retorna nada 

#=============================================================================#


def dump_stats(myStats):
    """
    Mostrar estatísticas quando pings são feitos
    """
    print("\n----%s PYTHON 3 PING Estatisticas----" % (myStats.thisIP))

    if myStats.pktsSent > 0:
        myStats.fracLoss = (myStats.pktsSent -
                            myStats.pktsRcvd)/myStats.pktsSent # (pacotes enviados - pacotes recebidos) / pacotes enviados = fracassos

    print("%d pacotes transmitidos, %d pacotes recebidos, %0.1f%% pacotes perdidos" % (
        myStats.pktsSent, myStats.pktsRcvd, 100.0 * myStats.fracLoss
    ))

    if myStats.pktsRcvd > 0:
        print("Round-trip time (RTT) (ms)  min/media/max = %d/%0.1f/%d" % (
            myStats.minTime, myStats.totTime/myStats.pktsRcvd, myStats.maxTime # mínimo, médio e máximo
        ))
    
    # armazenando esses dados na lista
    lista.append({'Minimo':myStats.minTime , 'Media':myStats.totTime/myStats.pktsRcvd, 'Maximo': myStats.maxTime})

    print("")
    return

#=============================================================================#


def verbose_ping(hostname, timeout=WAIT_TIMEOUT, count=NUM_PACKETS,
                 packet_size=PACKET_SIZE):
    """
    Envia > contador <ping para> destIP <com o tempo limite especificado> e exiba
    o resultado.
    """
    myStats = MyStats()  # Reseta o status

    mySeqNumber = 0  # Inicializando mySeqNumber

    try:
        destIP = socket.gethostbyname(hostname) # Pega endereco do IP do host
        print("\nPYTHON 3 PING %s (%s): %d com bytes de dados" %
              (hostname, destIP, packet_size)) # nome do host, ip destino e tamnanho do pacote 
    except socket.gaierror as e: # Essa gerada para erros ao host
        print(hostname) # nome do host
        print()
        return

    myStats.thisIP = destIP # atribui o ip destino do host ao ip do Objeto myStats

    for i in range(count):
        delay = atraso(myStats, destIP, hostname, 
                       timeout, mySeqNumber, packet_size)

        if delay == None:
            delay = 0

        mySeqNumber += 1

        # Aguarde para o restante do período MAX_SLEEP (se for verdade)
        if (MAX_SLEEP > delay):
            time.sleep((MAX_SLEEP - delay)/1000)

    dump_stats(myStats)

#=============================================================================#

def verificaHost(hostname):
 """
 verifica se o hostname é inválido ou não 
 """
 msg = "" # inicializando uma string vazia
 try:
  socket.gethostbyname(hostname)  # retorna o endereço de ip
  return hostname # retorna o host válido
 except socket.error: # se não possui host válido uma exceção é disparada
  msg = "A solicitação ping não pôde encontrar o host %s. Verifique o nome e tente novamente."%(hostname)
  return msg # retorna a msg com erro informando o usuário

#=============================================================================#

def escreveArquivo():
    """
    escreve num arquivo csv as estatísticas geradas pelo programa ping
    """

    minimo = 0 # contador mínimo
    medio = 0   # contador médio
    maximo = 0  # # contador máximo

    with open('dataset.csv', 'w', newline='') as csvfile:
        fieldnames = ['Minimo', 'Media', 'Maximo' ] # cabeçalho do arquivo
        # escrevendo o arquivo com as informações do dicionário lista
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames, delimiter =';',quotechar =',',quoting=csv.QUOTE_MINIMAL)
        
        writer.writeheader() # ler o cabeçalho
        for dicts in lista:
            tempMetricas = []
            tempValores = []
            for keys in dicts.keys():
                tempMetricas.append(keys)   # pega as chaves e coloca na lista de tempValores
            for valores in dicts.values():
                tempValores.append(valores) # pega as valores e coloca na lista de tempMetricas
            for i in range(len(tempMetricas)):
                if 'Minimo' == tempMetricas[i]:
                    minimo = round(tempValores[i],2) # coloca os valores da listaMetricas percorrida valores na váriavel mínimo
                if 'Media' == tempMetricas[i]:
                    medio = round(tempValores[i],2)  # coloca os valores da listaMetricas percorrida valores na váriavel medio
                if 'Maximo' == tempMetricas[i]:
                    maximo = round(tempValores[i],2)  # coloca os valores da listaMetricas percorrida valores na váriavel máximo
            writer.writerow({'Minimo': minimo, 'Media': medio, 'Maximo': maximo }) # escreve por linha em formato dicionário, atribuindo cada valor a sua chave especificada em fieldnames
        csvfile.close()

#=============================================================================#


def main():

    ping = verbose_ping 
    ping(verificaHost('www.wikipedia.org'), timeout=3000) # tentativa de ping no wikipedia
    ping(verificaHost('99.84.24.9'), timeout=3000) # tentativa de ping no ip da amazon
    ping(verificaHost('www.google.com'), timeout=3000) # tentativa de ping no google
    ping(verificaHost('localhost'), timeout=3000) # tentativa de ping no localhost
    ping(verificaHost('fla2019.com'), timeout=3000) # pingando em sites que não existem 
    ping(verificaHost('ZeldaGOT.com'), timeout=3000) # pingando em sites que não existem

    escreveArquivo()

if __name__ == '__main__':
    main()
