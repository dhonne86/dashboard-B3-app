import React, { useState, useEffect } from 'react';
import axios from 'axios';

function App() {
  const [acoes, setAcoes] = useState([]);
  const [indices, setIndices] = useState([]);

  useEffect(() => {
    axios.get('http://localhost:5000/api/acoes')
      .then(response => {
        setAcoes(response.data);
      })
      .catch(error => {
        console.error(error);
      });

    axios.get('http://localhost:5000/api/indices')
      .then(response => {
        setIndices(response.data);
      })
      .catch(error => {
        console.error(error);
      });
  }, []);

  return (
    <div>
      <h1>Dashboard de Mercado Financeiro</h1>
      <h2>Ações</h2>
      <table>
        <thead>
          <tr>
            <th>Data</th>
            <th>Abertura</th>
            <th>Alta</th>
            <th>Baixa</th>
            <th>Fechamento</th>
          </tr>
        </thead>
        <tbody>
          {acoes.map((acao, index) => (
            <tr key={index}>
              <td>{acao.Date}</td>
              <td>{acao.Open}</td>
              <td>{acao.High}</td>
              <td>{acao.Low}</td>
              <td>{acao.Close}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <h2>Índices</h2>
      <table>
        <thead>
          <tr>
            <th>Data</th>
            <th>Abertura</th>
            <th>Alta</th>
            <th>Baixa</th>
            <th>Fechamento</th>
          </tr>
        </thead>
        <tbody>
          {indices.map((indice, index) => (
            <tr key={index}>
              <td>{indice.Date}</td>
              <td>{indice.Open}</td>
              <td>{indice.High}</td>
              <td>{indice.Low}</td>
              <td>{indice.Close}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default App;